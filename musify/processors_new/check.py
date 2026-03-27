import itertools
import math
from collections.abc import Mapping, Sequence, Collection, Iterable, MutableSequence
from copy import deepcopy, copy
from typing import Annotated, Self, Any, Counter

from pydantic import Field, PositiveInt, PrivateAttr, field_validator
from termcolor import colored

from musify.models import ResourceModel
from musify.models.api import RemoteAPI, HasSavedEndpoints, HasAPI
from musify.models.api.playlist import HasPlaylistEndpoints, PlaylistReadWriteSavedEndpoints, PlaylistReadWriteEndpoints
from musify.models.collection import CollectionModel
from musify.models.collection.playlist import RemoteMutablePlaylist, RemotePlaylist
from musify.models.exception import MusifyValidationError
from musify.models.properties.name import HasName
from musify.models.properties.uri import HasURI, URI, HasMutableURI
from musify.models.remote import RemoteResource
from musify.models.result import Result, LenLogFormatter
from musify.models.sequence import UniqueSequence
from musify.models.user import RemoteUser
from musify.processors_new._base import InputProcessor
from musify.processors_new.formatter import CollectionFormatter
from musify.processors_new.match import Matcher
from musify.processors_new.match.score.string import NameScorer


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
    unchanged: Annotated[
        tuple[T, ...],
        LenLogFormatter(
            width=6, alignment="right", colour="blue", colour_attributes=["bold"], condition=lambda x: x == 0
        ),
        LenLogFormatter(
            width=6, alignment="right", colour="green", colour_attributes=["bold"], condition=lambda x: x > 0
        ),
    ] = Field(
        description="The items that weren't changed during the check.",
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
        tuple[ResourceModel, ...],
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
    _collections: dict[URI, CollectionModel] = PrivateAttr(
        # description="The collections currently being checked mapped to the URIs of the active playlists."
        default={},
    )
    _playlists: dict[URI, RemoteMutablePlaylist] = PrivateAttr(
        # description="The playlists relating to the collections being checked mapped to their URIs."
        default={},
    )
    _playlists_initial: dict[URI, RemoteMutablePlaylist] = PrivateAttr(
        # description="The initial state of the playlists relating to the collections being checked mapped to the URIs."
        default={},
    )

    api: API = Field(
        description="The API to use for checking matches.",
    )
    matcher: Matcher = Field(
        description=(
            "The matcher to use for confirming closest matches returned by the API "
            "when comparing changes in playlists"
        ),
        default_factory=lambda: Matcher(scorers=[NameScorer()]),
    )

    interval: PositiveInt = Field(
        description="The number of playlists to create before pausing for user input.",
        default=10,
    )
    formatter: CollectionFormatter[RemotePlaylist] = Field(
        description="The formatter to use for formatting info about the playlists during the check.",
        default_factory=lambda: CollectionFormatter[RemotePlaylist](
            fields=("Name", "URI", "Public URL"),
            colours=("white", "red", "yellow"),
            header=False,
        )
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

    @field_validator("playlist_properties", mode="after", check_fields=True)
    @classmethod
    def _validate_name_not_in_playlist_properties(cls, properties: dict[str, Any]) -> dict[str, Any]:
        if (key := "name") in properties:
            raise MusifyValidationError(
                f"{key!r} cannot be set in playlist properties as it is used to set the playlist name."
            )
        return properties

    @property
    def source(self) -> str:
        """The name of the remote service that this searcher is running on."""
        return self.api.source.title()

    @property
    def user(self) -> RemoteUser | None:
        """The user to create playlists for."""
        return self.api.playlists.user

    @property
    def _has_playlists(self) -> bool:
        """Whether there are any active temporary playlists being used for checking."""
        return len(self._playlists) > 0 or len(self._playlists_initial) > 0

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
        collections = [
            coll for coll in collections
            if coll.count > 0 and any(isinstance(item, HasURI) for item in coll.iter_items)
        ]
        if len(collections) == 0:
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
                should_continue = await self._run_pause_page(page=page, total=pages)

            except KeyboardInterrupt:
                self.logger.error("User triggered exit with KeyboardInterrupt")
            finally:
                if self._has_playlists:
                    await self._teardown_playlists()

            if not should_continue:
                break

    ###########################################################################
    ## Playlist management
    ###########################################################################
    async def _setup_playlist[T: ResourceModel](
            self, collection: CollectionModel[T]
    ) -> RemoteMutablePlaylist[T] | None:
        api: PlaylistReadWriteSavedEndpoints = self.api.playlists.saved
        name = collection.name if isinstance(collection, HasName) else str(id(collection))

        if self.use_existing_playlists:
            playlist: RemoteMutablePlaylist = await api.get_or_create(name=name, **self.playlist_properties)
        else:
            playlist: RemoteMutablePlaylist = await api.create(name=name, **self.playlist_properties)

        self._collections[playlist.uri] = collection
        self._playlists[playlist.uri] = playlist
        self._playlists_initial[playlist.uri] = deepcopy(playlist)

        playlist.tracks.extend(item for item in collection.iter_items if isinstance(item, HasURI) and item.has_uri)
        await playlist.sync_items(api=self.api, kind="refresh", dry_run=False, show_bar=False)

        await api.follow(playlist.uri.api_url)  # ensure the playlist appears in the user's library

    async def _teardown_playlists(self) -> None:
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

    async def _teardown_playlist(self, playlist: RemoteMutablePlaylist) -> None:
        if playlist.count != 0:
            # playlist existed before the check and should be returned to its original state
            await playlist.sync_items(api=self.api, kind="refresh", dry_run=False, show_bar=False)

        else:
            # otherwise, assume playlist was created by the checker and can be deleted directly
            api: PlaylistReadWriteEndpoints = self.api.playlists
            uris = [it.uri for it in self._playlists[playlist.uri].iter_items]
            await api.remove(playlist.uri.api_url, uris=uris, show_bar=False)

            api: PlaylistReadWriteSavedEndpoints = self.api.playlists.saved
            await api.delete(playlist.uri.api_url)

        del self._collections[playlist.uri]
        del self._playlists[playlist.uri]
        del self._playlists_initial[playlist.uri]

    ###########################################################################
    ## Pagination
    ###########################################################################
    async def _run_pause_page(self, page: int, total: int) -> bool:
        help_text = self._format_help_text_for_pause_page()
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

                case "q":  # quit
                    if self._has_playlists:
                        await self._teardown_playlists()
                    return False

                case "l":
                    self._print_playlist_links()

                case name if (playlist := self._get_playlist_by_name(name)) is not None:
                    await self._print_playlist_items(playlist)

        return True

    def _format_help_text_for_pause_page(self) -> str:
        header = colored(
            f"Temporary playlists created on {self._log_library}. " +
            f"You may now check the items in each playlist on {self.source}.",
            "blue",
            attrs=["bold"],
        )

        options = {
            "<Name of playlist>":
                "Print info on items originally added to the playlist and the current items if different",
            "<Return/Enter>":
                "Once you have checked all playlist's items, continue on and check for any switches by the user",
            "l": "Print the names and links of playlists created",
            "s": "Check for changes on current playlists, but skip any remaining checks",
            "q": "Delete current temporary playlists and quit check",
            "h": "Show this dialogue again",
        }

        help_text = self._format_help_text(options=options, header=header)
        return help_text + "\n"

    def _get_playlist_by_name(self, name: str) -> RemoteMutablePlaylist | None:
        for playlist in self._playlists.values():
            if playlist.name.casefold() == name.casefold():
                return playlist

    def _print_playlist_links(self):
        header = colored("Created playlists", "blue", attrs=["bold"])
        rows = (f"{playlist.name} - {playlist.uri.public_url}" for playlist in self._playlists.values())
        playlists = "\n".join(self.logger.generate_message(row, header=3) for row in rows)
        self.logger.print_message(header + ":\n" + playlists + "\n")

    async def _print_playlist_items(self, playlist: RemoteMutablePlaylist) -> None:
        self.logger.print_message()

        missing_message = colored("No items available", "red", attrs=["bold"])

        header = colored(f"{playlist.name.upper()} - ORIGINAL", "yellow", attrs=["bold"])
        table = self.formatter.format(playlist, indices=True) or missing_message
        self.logger.print_message(header + ":\n" + table + "\n")

        api: PlaylistReadWriteEndpoints = self.api.playlists
        items = await api.get_all(playlist)
        if items == list(playlist.iter_items):
            return

        playlist = deepcopy(playlist)
        playlist.tracks.replace(items)

        header = colored(f"{playlist.name.upper()} - CURRENT", "green", attrs=["bold"])
        table = self.formatter.format(playlist, indices=True) or missing_message
        self.logger.print_message(header + ":\n" + table + "\n")

    ###########################################################################
    ## Match with playlist
    ###########################################################################
    async def _match_with_playlist[CT: HasURI](self, playlist: RemoteMutablePlaylist) -> CheckResult[CT]:
        self.logger.info(f"Checking for changes to items in {self.source} playlist: {playlist.name}", header=2)

        added, removed, unchanged, missing, invalid = await self._compare_with_playlist(playlist)

        if not added and not removed and not missing:
            message = "Playlist unchanged and no missing URIs, skipping match"
            self._log_match_debug("SKIP", playlist, message)
            return CheckResult(unchanged=unchanged, skipped=invalid)

        unavailable = removed + missing
        if not added:
            message = "No items added, skipping match"
            self._log_match_debug("SKIP", playlist, message)
            return CheckResult(unchanged=unchanged, unavailable=unavailable, skipped=invalid)

        if not any(isinstance(item, HasMutableURI) for item in unavailable):
            message = "No items with mutable URIs to match with added items, skipping match"
            self._log_match_debug("SKIP", playlist, message)
            return CheckResult(unchanged=unchanged, unavailable=unavailable, skipped=invalid)

        changed = self._match_with_others(playlist, items=unavailable, others=added)
        return CheckResult(changed=changed, unchanged=unchanged, unavailable=unavailable, skipped=invalid)

    async def _compare_with_playlist[CT: HasURI, RT: RemoteResource](
            self, playlist: RemoteMutablePlaylist[Any, RT, Any, Any],
    ) -> tuple[list[CT], list[CT], list[CT], list[CT], list[CT]]:
        initial = self._get_initial_playlist_items(playlist)
        current = await self._get_current_playlist_items(playlist)

        initial_unique = UniqueSequence(initial)
        current_unique = UniqueSequence(current)

        added = list(current_unique.difference(initial_unique))
        removed = list(current_unique.outer_difference(initial_unique))
        removed += self._get_removed_duplicate_playlist_items(removed, initial, current)
        unchanged = list(current_unique.intersection(initial_unique))
        missing = self._get_missing_playlist_items(playlist)
        invalid = self._get_invalid_collection_items(playlist)

        if self.use_existing_playlists and self._playlists_initial[playlist.uri].count > 0:
            discount = self._playlists_initial[playlist.uri].count
            discount_message = "items that were in the playlist before starting"
            self._log_match_debug("REMOTE", playlist, discount_message, discount)

        self._log_match_debug("REMOTE", playlist, "items initially added to the playlist", len(initial))
        self._log_match_debug("REMOTE", playlist, "items that are confirmed as unavailable", len(invalid))
        self._log_match_debug("REMOTE", playlist, "items added", len(added))
        self._log_match_debug("REMOTE", playlist, "items removed", len(removed))
        self._log_match_debug("REMOTE", playlist, "items unchanged", len(unchanged))
        self._log_match_debug("REMOTE", playlist, "items still with missing URI", len(missing))
        self._log_match_debug("REMOTE", playlist, "total item changes", len(added) - len(removed))

        return added, removed, unchanged, missing, invalid

    def _get_initial_playlist_items[CT: HasURI](self, playlist: RemoteMutablePlaylist) -> list[CT]:
        collection = self._collections[playlist.uri]
        return [item for item in collection.iter_items if isinstance(item, HasURI) and item.has_uri]

    async def _get_current_playlist_items[RT: RemoteResource](
            self, playlist: RemoteMutablePlaylist[Any, RT, Any, Any]
    ) -> list[RT]:
        api: PlaylistReadWriteEndpoints = self.api.playlists
        current_items = await api.get_all(playlist.uri.api_url)

        # remove items that were present before checking started
        for item in self._playlists_initial[playlist.uri].iter_items:
            if item in current_items:
                current_items.remove(item)

        return [item for item in current_items if item.has_uri]

    @staticmethod
    def _get_removed_duplicate_playlist_items[CT: HasURI](
            removed: list[CT], initial: Collection[CT], current: Iterable[HasURI]
    ) -> list[CT]:
        # if item collection originally contained duplicate URIS and one or more of the duplicates were removed
        # find removed duplicate items by looking for changes in counts
        initial_counts = Counter(item.uri for item in initial)
        current_counts = Counter(item.uri for item in current)
        removed_counts = Counter(item.uri for item in removed)

        removed_duplicates = []
        for item in initial:
            initial_count = initial_counts.get(item.uri, 0)
            current_count = current_counts.get(item.uri, 0)
            removed_count = removed_counts.get(item.uri, 0)

            if initial_count == 1 or initial_count <= removed_count + current_count:
                continue

            removed_duplicates.append(item)
            removed_counts = Counter(item.uri for item in removed + removed_duplicates)  # refresh counts

        return removed_duplicates

    def _get_missing_playlist_items[CT: HasURI](self, playlist: RemoteMutablePlaylist) -> list[CT]:
        collection = self._collections[playlist.uri]
        return [item for item in collection.iter_items if isinstance(item, HasURI) and item.has_uri is None]

    def _get_invalid_collection_items[CT: ResourceModel](self, playlist: RemoteMutablePlaylist) -> list[CT]:
        collection = self._collections[playlist.uri]
        return [item for item in collection.iter_items if not isinstance(item, HasURI) or item.has_uri is False]

    ###########################################################################
    ## Match with input
    ###########################################################################
    # TODO

    ###########################################################################
    ## Match - misc.
    ###########################################################################
    def _match_with_others[CT: HasURI](
            self, playlist: RemoteMutablePlaylist, items: MutableSequence[CT], others: MutableSequence[CT]
    ) -> list[CT]:
        initial = len(items)
        changed = []

        for item in copy(items):  # copy to safely modify items while iterating
            if not isinstance(item, HasMutableURI):
                continue
            if not others:
                break

            match = self.matcher.match(item, others)
            if match is None or not match.has_uri:
                continue

            messages = [f"Updating {item.type} URI", f"{item.uri} -> {match.uri}"]
            self._log_match_debug("REMOTE", item, messages, pad="<")
            item.uri = match.uri

            changed.append(item)
            items.remove(item)
            others.remove(match)

        final = len(items)
        self._log_match_debug("REMOTE", playlist, "items switched", initial - final)
        self._log_match_debug("REMOTE", playlist, "items still not found", final)

        return changed

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

        username = self.user.name if self.user is not None else "the current user"
        message = (
            f"Checking items in {len(collections)} {collection_types_str} by creating "
            f"temporary {self.source} playlists for {username}"
        )
        self.logger.info(message, header=1)

    def _log_skip(self) -> None:
        self.logger.extra(colored("No valid collections or items to check.", "yellow"))

    def _log_match_debug(self, method: str, item: Any, messages: str | Iterable, count: int | None = None, pad: str = " ") -> None:
        if count is not None and isinstance(messages, str):
            messages = f"{count:>6} {messages}"

        log = self._format_item_message(method=method, item=item, messages=messages, pad=pad)
        self.logger.debug(log)
