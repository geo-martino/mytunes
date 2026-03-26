import itertools
import math
from collections.abc import Mapping, Sequence
from copy import deepcopy
from typing import Annotated, Self, Any

from pydantic import Field, PositiveInt, PrivateAttr, field_validator
from termcolor import colored

from musify.models import ResourceModel
from musify.models.api import RemoteAPI, HasSavedEndpoints, HasAPI
from musify.models.api.playlist import HasPlaylistEndpoints, PlaylistReadWriteSavedEndpoints, PlaylistReadWriteEndpoints
from musify.models.collection import CollectionModel
from musify.models.collection.playlist import RemoteMutablePlaylist
from musify.models.exception import MusifyValidationError
from musify.models.properties.name import HasName
from musify.models.properties.uri import HasURI, URI, item_has_uri
from musify.models.result import Result, LenLogFormatter
from musify.models.user import RemoteUser
from musify.processors_new._base import InputProcessor
from musify.processors_new.match import Matcher


class CheckResult[T: HasURI](Result):
    """Stores the results of the searching process."""
    changed: Annotated[
        tuple[T, ...],
        LenLogFormatter(
            width=6, alignment="right", colour="blue", colour_attributes=["bold"], condition=lambda x: x == 0
        ),
        LenLogFormatter(
            width=6, alignment="right", colour="green", colour_attributes=["bold"], condition=lambda x: x > 0
        ),
    ] = Field(
        description="The items that had their matches changed during the check.",
        default_factory=tuple
    )
    unavailable: Annotated[
        tuple[T, ...],
        LenLogFormatter(
            width=6, alignment="right", colour="green", colour_attributes=["bold"], condition=lambda x: x == 0
        ),
        LenLogFormatter(
            width=6, alignment="right", colour="yellow", colour_attributes=["bold"], condition=lambda x: x > 0
        ),
    ] = Field(
        description="The items that were marked as unavailable during the check.",
        default_factory=tuple
    )
    skipped: Annotated[
        tuple[T, ...],
        LenLogFormatter(
            width=6, alignment="right", colour="green", colour_attributes=["bold"], condition=lambda x: x == 0
        ),
        LenLogFormatter(
            width=6, alignment="right", colour="blue", colour_attributes=["bold"], condition=lambda x: x > 0
        ),
    ] = Field(
        description="The items that were skipped during the check.",
        default_factory=tuple
    )


type _ApiT = RemoteAPI | HasPlaylistEndpoints[
    PlaylistReadWriteEndpoints |
    HasSavedEndpoints[PlaylistReadWriteSavedEndpoints]
]


class Checker[API: _ApiT](InputProcessor, HasAPI):
    _playlists_initial: dict[URI, RemoteMutablePlaylist] = PrivateAttr(
        # description="The initial state of the playlists before the checking process."
        default={},
    )
    _playlists: dict[URI, RemoteMutablePlaylist] = PrivateAttr(
        # description="The state of the playlists during the checking process."
        default={},
    )

    api: API = Field(
        description="The API to use for checking matches.",
    )
    matcher: Matcher | None = Field(
        description=(
            "The matcher to use for confirming closest matches returned by the API "
            "when comparing changes in playlists"
        ),
        default=None,
    )

    interval: PositiveInt = Field(
        description="The number of playlists to create before pausing for user input.",
        default=10,
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

    playlist_properties: dict[str, Any] = Field(
        description=(
            "Optional properties to set on the temporary playlists created for checking matches. "
            "You must ensure that the properties provided are valid for the API being used or the process may fail."
        ),
        default_factory=dict,
    )

    @property
    def source(self) -> str:
        """The name of the remote service that this searcher is running on."""
        return self.api.source.title()

    @property
    def user(self) -> RemoteUser | None:
        """The user to create playlists for."""
        return self.api.playlists.user

    @field_validator("api", mode="after")
    @classmethod
    def _validate_api_has_necessary_endpoints(cls, api: _ApiT) -> _ApiT:
        if not isinstance(api, RemoteAPI):
            raise MusifyValidationError(f"API must be an instance of RemoteAPI, got {type(api)}")
        if not isinstance(api, HasPlaylistEndpoints):
            raise MusifyValidationError(f"API does not support playlist endpoints")
        if not isinstance(api.playlists, PlaylistReadWriteEndpoints):
            raise MusifyValidationError(f"API does not support writing data for playlists")
        if not isinstance(api.playlists, HasSavedEndpoints):
            raise MusifyValidationError(f"API does not support saved playlist endpoints")
        if not isinstance(api.playlists.saved, PlaylistReadWriteSavedEndpoints):
            raise MusifyValidationError(f"API does not support writing data for saved playlists")

        return api

    async def __aenter__(self) -> Self:
        await self.api.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.api.__aexit__(exc_type, exc_val, exc_tb)

    async def check[T: ResourceModel](self, collections: Sequence[CollectionModel[T]]) -> dict[str, CheckResult[T]]:
        """Check the matches for the given collection and return the results."""
        if len(collections) == 0 or sum(collection.count for collection in collections) == 0:
            self._log_skip()
            return {}

        self._log_start(collections)

        total = len(collections)
        pages = math.ceil(total / self.interval)
        bar = self.logger.get_synchronous_iterator(
            iter(collections), total=total, desc="Creating playlists", unit="playlists"
        )

        should_continue = True

        for page in range(1, pages + 1):
            try:
                await self.logger.get_asynchronous_iterator(
                    map(self._setup_playlist, itertools.islice(bar, self.interval)), disable=True,
                )
                should_continue = await self._pause(page=page, total=pages)

            except KeyboardInterrupt:
                self.logger.error("User triggered exit with KeyboardInterrupt")
            finally:
                await self._teardown_playlists()

            if not should_continue:
                break

    async def _setup_playlist[T: ResourceModel](
            self, collection: CollectionModel[T]
    ) -> RemoteMutablePlaylist[T] | None:
        if collection.count == 0:
            return

        api: PlaylistReadWriteSavedEndpoints = self.api.playlists.saved
        name = collection.name if isinstance(collection, HasName) else str(id(collection))

        if self.use_existing_playlists:
            playlist: RemoteMutablePlaylist = await api.get_or_create(name=name, **self.playlist_properties)
        else:
            playlist: RemoteMutablePlaylist = await api.create(name=name, **self.playlist_properties)

        self._playlists_initial[playlist.uri] = deepcopy(playlist)
        self._playlists[playlist.uri] = playlist

        playlist.tracks.extend(item for item in collection.iter_items if item_has_uri(item))
        await playlist.sync_items(api=self.api, kind="refresh", dry_run=False, show_bar=False)

        await api.follow(playlist.uri.api_url)  # ensure the playlist appears in the user's library

    async def _teardown_playlists(self) -> None:
        if not self._playlists_initial:
            return

        # assume all empty original playlists were temp playlists and delete them, restore the others
        delete_count = sum(pl.count == 0 for pl in self._playlists_initial.values())
        restore_count = sum(pl.count > 0 for pl in self._playlists_initial.values())

        message = f"Deleting {delete_count} temporary playlists and restoring {restore_count} playlists"
        self.logger.extra(message, header=3)

        await self.logger.get_asynchronous_iterator(
            map(self._teardown_playlist, self._playlists_initial.values()),
            desc="Restoring/deleting",
            unit="playlists",
            total=len(self._playlists_initial),
        )

        self._playlists_initial.clear()
        self._playlists.clear()

    async def _teardown_playlist(self, playlist: RemoteMutablePlaylist) -> None:
        if playlist.count != 0:
            # playlist existed before the check and should be returned to its original state
            await playlist.sync_items(api=self.api, kind="refresh", dry_run=False, show_bar=False)
            return

        # otherwise, assume playlist was created by the checker and can be deleted directly
        api: PlaylistReadWriteEndpoints = self.api.playlists
        uris = [track.uri for track in self._playlists[playlist.uri].tracks]
        await api.remove(playlist.uri.api_url, uris=uris, show_bar=False)

        api: PlaylistReadWriteSavedEndpoints = self.api.playlists.saved
        await api.delete(playlist.uri.api_url)

    async def _pause(self, page: int, total: int) -> bool:
        help_text = self._format_help_text_for_pause()
        self.logger.print_message("\n" + help_text)

        while True:
            value = self._get_user_input(f"Enter ({page}/{total})")

            match value.casefold():
                case "":  # continue to next batch
                    break

                case "h":  # print help text
                    self.logger.print_message("\n" + help_text)

                case "s":  # skip
                    return False

        return True

    def _format_help_text_for_pause(self) -> str:
        header = colored(
            f"Temporary playlists created on {self._log_library}. " +
            f"You may now check the items in each playlist on {self.source}.",
            "blue",
            attrs=["bold"],
        )

        options = {
            "<Name of playlist>":
                "Print position, item name, URI, and URL from given link of items as originally added to temp playlist",
            f"<{self.source} URL/URI>":
                "Print position, item name, URI, and URL from given link (useful to check current status of playlist)",
            "<Return/Enter>":
                "Once you have checked all playlist's items, continue on and check for any switches by the user",
            "l": "List the names of the temporary playlists created",
            "s": "Check for changes on current playlists, but skip any remaining checks",
            "q": "Delete current temporary playlists and quit check",
            "h": "Show this dialogue again",
        }

        playlist_names = [playlist.name for playlist in self._playlists.values()]
        playlist_names_message = f"\n\nAvailable playlists: {", ".join(playlist_names)}"

        help_text = self._format_help_text(options=options, header=header)
        help_text += colored(playlist_names_message, "dark_grey")

        return help_text + "\n"

    ###########################################################################
    ## Logging
    ###########################################################################
    def log_results(self, results: Mapping[str, CheckResult]) -> None:
        """Log the given check results"""
        header = f"{self.source.upper()} CHECK RESULTS"
        table = CheckResult.generate_table(results=results, header=header)
        self.logger.report(table)

    @property
    def _log_library(self) -> str:
        source = self.source.title()
        if self.user is None:
            return source
        return f"{self.user.name}'s {source} library"

    def _log_start(self, collections: Sequence[CollectionModel]) -> None:
        collection_types = sorted({
            collection.type.rstrip("s") + "s" for collection in collections if isinstance(collection, ResourceModel)
        })

        collection_types_str = ", ".join(collection_types[:-1])
        if collection_types_str:
            collection_types_str = " & ".join([collection_types_str, collection_types[-1]])
        else:
            collection_types_str = collection_types[0]

        message = (
            f"Checking items in {len(collections)} {collection_types_str} by creating "
            f"temporary {self.source} playlists for the current user: {self.user.name}"
        )
        self.logger.info(message, header=1)

    def _log_skip(self) -> None:
        self.logger.extra(colored("No collections or items to check.", "yellow"))