import asyncio
from collections.abc import Iterable, Collection, Sequence
from collections.abc import MutableMapping
from copy import deepcopy
from typing import Self, Any, ClassVar

from aiorequestful.exception import HTTPError
from pydantic import Field, field_validator, PrivateAttr, PositiveFloat
from rich.progress import TaskID
from termcolor import colored

from musify.exception import MusifyError
from musify.models.api import RemoteAPI, HasAPI, HasLibraryEndpoints
from musify.models.api.playlist import PlaylistLibraryEndpoints, PlaylistReadWriteEndpoints, \
    HasPlaylistEndpoints, PlaylistBatchWriteEndpoints
from musify.models.collection import CollectionModel
from musify.models.collection.playlist import RemoteMutablePlaylist, RemotePlaylist
from musify.models.cursors import InitialCursor
from musify.models.exception import MusifyValidationError
from musify.models.properties.asynch import HasAsyncOperations
from musify.models.properties.name import HasName
from musify.models.properties.uri import HasURI, URI
from musify.models.remote import RemoteResource
from musify.models.user import RemoteUser
from musify.processors._base import PageProcessor
from musify.processors._exception import QuitImmediately, SkipPage
from musify.processors.formatter import CollectionFormatter

type _ApiT = RemoteAPI | HasPlaylistEndpoints[
    PlaylistReadWriteEndpoints |
    HasLibraryEndpoints[PlaylistLibraryEndpoints]
]


class CheckerPage[API: _ApiT, CT: HasURI](PageProcessor, HasAPI[API], HasAsyncOperations):
    #: The time to wait after adding tracks to a playlist on setup.
    wait_after_add: ClassVar[PositiveFloat] = 0.8

    _collections: MutableMapping[URI, CollectionModel[CT]] = PrivateAttr(
        # description="The collections currently being checked mapped to the URIs of the active playlists.",
        default_factory=dict,
    )
    _playlists: MutableMapping[URI, RemoteMutablePlaylist] = PrivateAttr(
        # description="The playlists relating to the collections being checked mapped to their URIs.",
        default_factory=dict,
    )
    _playlists_initial: MutableMapping[URI, RemoteMutablePlaylist] = PrivateAttr(
        # description=(
        #     "The initial state of the playlists relating to the collections being checked mapped to the URIs."
        # ),
        default_factory=dict,
    )

    collections: Sequence[CollectionModel] = Field(
        description="The collections to be checked on this page."
    )

    additional_properties: dict[str, Any] = Field(
        description=(
            "Optional properties to set on the temporary playlists created for checking matches. "
            "You must ensure that the properties provided are valid for the API being used or the process may fail."
        ),
        default_factory=dict,
    )
    use_existing_playlists: bool = Field(
        description=(
            "Whether to use existing playlists in the user's library for checking matches if available. "
            "If True, this will modify any existing playlists with the same name as the collections being "
            "checked during the process and then attempt to return them to their original state at the end, "
            "so use with caution. "
            "If False, new playlists will always be created for checking matches regardless of existing playlists. "
            "This may result in name clashes on some remote services."
        ),
        default=False,
    )

    playlist_formatter: CollectionFormatter[RemotePlaylist] = Field(
        description="The formatter to use for formatting info about the playlists during the check.",
        default=CollectionFormatter[RemotePlaylist](
            fields=("Name", "URI", "Public URL"),
            colours=("white", "red", "yellow"),
            header=False,
        )
    )

    @field_validator("api", mode="after")
    @classmethod
    def _validate_api_has_necessary_endpoints(cls, api: _ApiT) -> _ApiT:
        if not isinstance(api, RemoteAPI):
            raise MusifyValidationError(f"API must be an instance of RemoteAPI, got {type(api).__name__!r}")
        if not isinstance(api, HasPlaylistEndpoints):
            raise MusifyValidationError(f"API does not support playlist endpoints")
        if not isinstance(api.playlists, PlaylistReadWriteEndpoints):
            raise MusifyValidationError(f"API does not support writing data for playlists")
        if not isinstance(api.playlists, HasLibraryEndpoints):
            raise MusifyValidationError(f"API does not support library playlist endpoints")
        if not isinstance(api.playlists.library, PlaylistLibraryEndpoints):
            raise MusifyValidationError(f"API does not support writing data for library playlists")

        return api

    @property
    def source(self) -> str:
        """The log name of the remote service that this searcher is running on."""
        return self.api.source.title()

    @property
    def user(self) -> RemoteUser | None:
        """The user to create playlists for."""
        return self.api.playlists.user

    @property
    def count(self) -> int:
        """The number of collections to be checked."""
        return len(self.collections)

    @property
    def names(self) -> Iterable[str]:
        """The names of the playlists being used for checking."""
        return (pl.name for pl in self._playlists.values())

    @property
    def uris(self) -> Iterable[URI]:
        """The URIs of the playlists being used for checking."""
        return self._playlists.keys()

    @field_validator("additional_properties", mode="after", check_fields=True)
    @classmethod
    def _validate_name_not_in_additional_properties(cls, properties: dict[str, Any]) -> dict[str, Any]:
        if (key := "name") in properties:
            raise MusifyValidationError(
                f"{key!r} cannot be set in playlist properties as it is used to set the playlist name."
            )
        return properties

    async def __aenter__(self) -> Self:
        await super().__aenter__()
        if self.task_id is not None:
            self.logger.progress.start_task(task_id=self.task_id)

        try:
            async with asyncio.TaskGroup() as tg:
                tasks = [tg.create_task(task) for task in map(self._setup_playlist, self.collections)]
                remove = self.position.number == self.position.total
                await self.logger.run_tasks_async(tasks, task_id=self.task_id, remove=remove)
        except* (MusifyError, HTTPError):
            # always make sure teardown happens in case of an error to clean up temp playlists
            await self.teardown_playlists()
            raise

        if self.task_id is not None and not remove:
            self.logger.progress.stop_task(task_id=self.task_id)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.teardown_playlists()
        return await super().__aexit__(exc_type, exc_val, exc_tb)

    ###########################################################################
    ## Playlist setup/teardown
    ###########################################################################
    async def setup_playlists(self) -> None:
        """Set up the playlists for the given collections and store their state."""
        tasks = [asyncio.create_task(task) for task in map(self._setup_playlist, self.collections)]
        remove = self.position.number == self.position.total
        await self.logger.run_tasks_async(tasks, task_id=self.task_id, remove=remove)

    async def _setup_playlist(self, collection: CollectionModel) -> RemoteMutablePlaylist | None:
        api: PlaylistReadWriteEndpoints = self.api.playlists
        api_library: PlaylistLibraryEndpoints = self.api.playlists.library
        name = collection.name if isinstance(collection, HasName) else str(id(collection))

        async with self.concurrency:
            if self.use_existing_playlists:
                playlist: RemoteMutablePlaylist = await api_library.get_or_create(name=name, **self.additional_properties)
            else:
                playlist: RemoteMutablePlaylist = await api_library.create(name=name, **self.additional_properties)

            self._collections[playlist.uri] = collection
            self._playlists[playlist.uri] = playlist
            self._playlists_initial[playlist.uri] = deepcopy(playlist)

            # empty the playlist
            if playlist.count:
                playlist.tracks.clear()
                await playlist.sync_items(api=self.api, kind="refresh", dry_run=False, show_bar=False)

            # add all new uris
            uris = [item.uri for item in collection.items if isinstance(item, HasURI) and item.has_uri]
            await api.add(playlist.uri.api_url, uris=uris, show_bar=False)

            # WORKAROUND: it seems some APIs need some time between adding and getting items
            await asyncio.sleep(self.wait_after_add)

            # should help force an extension
            playlist.cursor = InitialCursor.from_url(playlist.cursor.url, source=playlist.source)
            await playlist.extend(self.api)  # refresh playlist items with just added URIs

    async def teardown_playlists(self) -> None:
        """
        Teardown the playlists used for checking by deleting any created by this process
        and restoring any that were not.
        """
        if not self._playlists:
            self.logger.extra("No playlists were created, skipping teardown")

        # all initially empty playlists were temp playlists - delete them, restore the others
        delete = [pl for pl in self._playlists_initial.values() if pl.count == 0]
        restore = [pl for pl in self._playlists_initial.values() if pl.count > 0]

        if delete:
            await self._delete_playlists(delete)
        if restore:
            await self._restore_playlists(restore)

    async def _delete_playlists(self, playlists: Collection[RemoteMutablePlaylist]) -> None:
        message = f"Deleting {len(playlists)} temporary playlists"
        self.logger.extra(message, header=3)

        uris = {pl.uri for pl in playlists}
        api: PlaylistBatchWriteEndpoints = self.api.playlists.library
        await api.remove_many(list(uris))

        for uri in uris:
            del self._collections[uri]
            del self._playlists[uri]
            del self._playlists_initial[uri]

    async def _restore_playlists(self, playlists: Collection[RemoteMutablePlaylist]) -> None:
        message = f"Restoring {len(playlists)} playlists"
        self.logger.extra(message, header=3)

        task_id = self.logger.progress.add_task(description="Restoring playlists", total=len(playlists))
        await self.logger.run_tasks_async(map(self._restore_playlist, playlists), task_id=task_id)

    async def _restore_playlist(self, playlist: RemoteMutablePlaylist) -> None:
        async with self.concurrency:
            # playlist existed before the check and should be returned to its original state
            await playlist.sync_items(api=self.api, kind="refresh", dry_run=False, show_bar=False)

        del self._collections[playlist.uri]
        del self._playlists[playlist.uri]
        del self._playlists_initial[playlist.uri]

    ###########################################################################
    ## Collection/Playlist state management
    ###########################################################################
    def get_collection_items(self, uri: URI) -> list[CT]:
        """Get the items in the collection with the given URI."""
        return list(self._collections[uri].items)

    def get_playlist_name(self, uri: URI) -> str:
        """Get the name of the playlist with the given URI."""
        return self._playlists[uri].name

    def get_initial_playlist_items(self, uri: URI) -> list[RemoteResource]:
        """Get the items that were in the playlist with the given URI before starting the check process."""
        return list(self._playlists_initial[uri].items)

    def get_stored_playlist_items(self, uri: URI) -> list[RemoteResource]:
        """
        Get the stored items in the playlist with the given URI.
        This may not be the same as the current items in the playlist on the remote service.
        """
        return list(self._playlists[uri].items)

    async def get_current_playlist_items(self, uri: URI) -> list[RemoteResource]:
        """Get the current items in the playlist with the given URI."""
        api: PlaylistReadWriteEndpoints = self.api.playlists
        current_playlist = await api.get(uri.api_url)
        current_items = await api.get_all(current_playlist)
        return [item for item in current_items if item.has_uri]

    async def refresh_playlist_items(self, uri: URI) -> None:
        """
        Update the stored state of the playlist with the given URI to reflect the current items in the
        playlist on the remote service.
        """
        items = await self.get_current_playlist_items(uri)
        playlist = self._playlists[uri]
        playlist.tracks.replace(items)

    ###########################################################################
    ## Pause page
    ###########################################################################
    @property
    def _header(self) -> str:
        source = f"{self.user.name}'s {self.source} library" if self.user is not None else self.source
        header = f"{len(self._playlists)} temporary playlists created on {source}. "
        header += f"You may now check the items in each playlist on {self.source}."
        return colored(header, "blue", attrs=["bold"])

    @property
    def _options(self) -> dict[str, str]:
        return {
            "<Name of playlist>":
                "Print info on items originally added to the playlist and the current items if different",
            "<Return/Enter>":
                "Once you have checked all playlist's items, continue on and check for any switches by the user",
            "l": "Print the names and links of playlists created",
            "s": "Don't check for changes and skip to the next set of playlists (if applicable)",
            "q": "Delete all temporary playlists and quit check",
        }

    async def pause(self) -> None:
        """
        Pause the check process and prompt the user to check and modify the created playlists
        on the remote service before continuing if they wish to.
        """
        super().pause()

        while option := self._get_user_input():
            match option.casefold():
                case "l":
                    self._print_playlist_links()

                case name if (playlist := self._get_playlist_by_name(name)) is not None:
                    await self._print_playlist_items(playlist)

                case _:
                    self._log_unrecognised_input(option)

    def _print_playlist_links(self):
        header = colored("Created playlists", "blue", attrs=["bold"])
        rows = (f"{playlist.name} - {playlist.uri.public_url}" for playlist in self._playlists.values())
        rows = (self.logger.generate_message(row, header=3) for row in sorted(rows))
        self.logger.print(header + ":\n" + "\n".join(rows) + "\n")

    def _get_playlist_by_name(self, name: str) -> RemoteMutablePlaylist | None:
        for playlist in self._playlists.values():
            if playlist.name.casefold() == name.casefold():
                return playlist

    async def _print_playlist_items(self, playlist: RemoteMutablePlaylist) -> None:
        self.logger.print()

        missing_message = colored("No items available", "red", attrs=["bold"])

        header = colored(f"{playlist.name.upper()} - ORIGINAL", "yellow", attrs=["bold"])
        table = self.playlist_formatter.format(playlist, indices=True) or missing_message
        self.logger.print(header + ":\n" + table + "\n")

        items = await self.get_current_playlist_items(playlist.uri)
        if items == list(playlist.items):
            return

        playlist = deepcopy(playlist)
        playlist.tracks.replace(items)

        header = colored(f"{playlist.name.upper()} - CURRENT", "green", attrs=["bold"])
        table = self.playlist_formatter.format(playlist, indices=True) or missing_message
        self.logger.print(header + ":\n" + table + "\n")
