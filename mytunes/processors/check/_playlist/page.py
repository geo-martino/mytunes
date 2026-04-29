import asyncio
from collections.abc import Iterable, Collection, Sequence
from collections.abc import MutableMapping
from typing import Self, Any, ClassVar

from aiorequestful.exception import HTTPError
from pydantic import Field, field_validator, PrivateAttr, PositiveFloat
from termcolor import colored

from mytunes.core.api import RemoteAPI, HasLibraryEndpoints
from mytunes.core.api.playlist import PlaylistLibraryEndpoints, PlaylistReadWriteEndpoints, \
    HasPlaylistEndpoints, BatchWriteEndpoints
from mytunes.core.collection import CollectionModel
from mytunes.core.cursors import InitialCursor
from mytunes.core.playlist import RemoteMutablePlaylist, RemotePlaylist
from mytunes.core.properties.name import HasName
from mytunes.core.properties.uri import HasURI, URI
from mytunes.core.remote import RemoteResource
from mytunes.exception import MyTunesError, MyTunesValidationError
from mytunes.processors.check._page import CheckerPage
from mytunes.processors.formatter import CollectionFormatter

type _ApiT = RemoteAPI | HasPlaylistEndpoints[
    PlaylistReadWriteEndpoints |
    HasLibraryEndpoints[PlaylistLibraryEndpoints]
]


class PlaylistsPage[API: _ApiT, CT: HasURI](CheckerPage[API, CT]):
    #: The time to wait after adding tracks to a playlist on setup.
    wait_after_add: ClassVar[PositiveFloat] = 0.8

    items: Sequence[CollectionModel] = Field(
        description="The collections to be checked on this page."
    )

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
        default=CollectionFormatter(
            fields=("Name", "URI", "Public URL"),
            colours=("white", "red", "yellow"),
            header=False,
        )
    )

    @field_validator("api", mode="after")
    @classmethod
    def _validate_api_has_necessary_endpoints(cls, api: API) -> API:
        api = super()._validate_api_has_necessary_endpoints(api)

        if not isinstance(api, HasPlaylistEndpoints):
            raise MyTunesValidationError(f"API does not support playlist endpoints")
        if not isinstance(api.playlists, PlaylistReadWriteEndpoints):
            raise MyTunesValidationError(f"API does not support writing data for playlists")
        if not isinstance(api.playlists, HasLibraryEndpoints):
            raise MyTunesValidationError(f"API does not support library playlist endpoints")
        if not isinstance(api.playlists.library, PlaylistLibraryEndpoints):
            raise MyTunesValidationError(f"API does not support writing data for library playlists")

        return api

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
            raise MyTunesValidationError(
                f"{key!r} cannot be set in playlist properties as it is used to set the playlist name."
            )
        return properties

    async def __aenter__(self) -> Self:
        await super().__aenter__()
        if self.task_id is not None:
            self._progress.start_task(task_id=self.task_id)

        try:
            await self.setup_playlists()
        except* (MyTunesError, HTTPError):
            # always make sure teardown happens in case of an error to clean up temp playlists
            await self.teardown_playlists()
            raise

        if self.task_id is not None and self.position.number < self.position.total:
            self._progress.stop_task(task_id=self.task_id)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.teardown_playlists()
        return await super().__aexit__(exc_type, exc_val, exc_tb)

    ###########################################################################
    ## Playlist setup/teardown
    ###########################################################################
    async def setup_playlists(self) -> None:
        """Set up the playlists for the given collections and store their state."""
        tasks = map(self._setup_playlist, self.items)
        remove = self.position.number == self.position.total
        await self._run_tasks_async(tasks, task_id=self.task_id, remove=remove)

    async def _setup_playlist(self, collection: CollectionModel) -> RemoteMutablePlaylist | None:
        api: PlaylistReadWriteEndpoints = self.api.playlists
        api_library: PlaylistLibraryEndpoints = self.api.playlists.library
        name = collection.name if isinstance(collection, HasName) else str(id(collection))

        async with self.concurrency:
            props = self.additional_properties
            if self.use_existing_playlists:
                playlist: RemoteMutablePlaylist = await api_library.get_or_create(name=name, **props)
            else:
                playlist: RemoteMutablePlaylist = await api_library.create(name=name, **props)

            self._collections[playlist.uri] = collection
            self._playlists[playlist.uri] = playlist
            self._playlists_initial[playlist.uri] = playlist.model_copy(deep=True)

            # empty the playlist
            if playlist.total:
                playlist.tracks.clear()
                await playlist.sync_items(api=self.api, kind="refresh", dry_run=False)

            # add all new uris
            uris = [item.uri for item in collection.items if isinstance(item, HasURI) and item.has_uri]
            await api.add(playlist.uri.api_url, uris=uris)

            # WORKAROUND: it seems some APIs need some time between adding and getting items
            await asyncio.sleep(self.wait_after_add)

            # should help force an extension
            playlist.__dict__["cursor"] = InitialCursor.from_url(playlist.cursor.url, source=playlist.source)
            await playlist.extend(self.api)  # refresh playlist items with just added URIs

    async def teardown_playlists(self) -> None:
        """
        Teardown the playlists used for checking by deleting any created by this process
        and restoring any that were not.
        """
        if not self._playlists:
            self._logger.extra("No playlists were created, skipping teardown")

        # all initially empty playlists were temp playlists - delete them, restore the others
        delete = [pl for pl in self._playlists_initial.values() if pl.total == 0]
        restore = [pl for pl in self._playlists_initial.values() if pl.total > 0]

        if delete:
            await self._delete_playlists(delete)
        if restore:
            await self._restore_playlists(restore)

    async def _delete_playlists(self, playlists: Collection[RemoteMutablePlaylist]) -> None:
        message = f"Deleting {len(playlists)} temporary playlists"
        self._logger.extra(message, header=3)

        uris = {pl.uri for pl in playlists}
        api: BatchWriteEndpoints = self.api.playlists.library
        await api.remove_many(list(uris))

        for uri in uris:
            del self._collections[uri]
            del self._playlists[uri]
            del self._playlists_initial[uri]

    async def _restore_playlists(self, playlists: Collection[RemoteMutablePlaylist]) -> None:
        message = f"Restoring {len(playlists)} playlists"
        self._logger.extra(message, header=3)

        task_id = self._progress.add_task(description="Restoring playlists", total=len(playlists))
        await self._run_tasks_async(map(self._restore_playlist, playlists), task_id=task_id)

    async def _restore_playlist(self, playlist: RemoteMutablePlaylist) -> None:
        async with self.concurrency:
            # playlist existed before the check and should be returned to its original state
            await playlist.sync_items(api=self.api, kind="refresh", dry_run=False)

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
        current_items = await api.get_all_items(current_playlist)
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
        source = f"{self.username}'s {self.source} library" if self.username is not None else self.source
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
        rows = map(str, (self._logger.generate_message(row, header=3) for row in sorted(rows)))
        self._logger.print(header + ":\n" + "\n".join(rows))
        self._logger.print_line()

    def _get_playlist_by_name(self, name: str) -> RemoteMutablePlaylist | None:
        for playlist in self._playlists.values():
            if playlist.name.casefold() == name.casefold():
                return playlist

    async def _print_playlist_items(self, playlist: RemoteMutablePlaylist) -> None:
        missing_message = colored("No items available", "red", attrs=["bold"])

        header = colored(f"{playlist.name.upper()} - ORIGINAL", "yellow", attrs=["bold"])
        table = self.playlist_formatter.format(playlist, indices=True) or missing_message
        self._logger.print(header + ":\n" + table)

        items = await self.get_current_playlist_items(playlist.uri)
        if items == list(playlist.items):
            self._logger.print_line()
            return

        playlist = playlist.model_copy(deep=True)
        playlist.tracks.replace(items)

        header = colored(f"{playlist.name.upper()} - CURRENT", "green", attrs=["bold"])
        table = self.playlist_formatter.format(playlist, indices=True) or missing_message
        self._logger.print(header + ":\n" + table)
        self._logger.print_line()
