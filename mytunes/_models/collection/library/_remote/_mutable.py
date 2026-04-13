from collections.abc import Collection, Mapping, Sequence
from typing import Any, Literal, Annotated

from aiorequestful.response.exception import ResponseError
from pydantic import Field, validate_call, BeforeValidator
from termcolor import colored

from mytunes._models.api import RemoteAPI, IsRemoteService, HasLibraryEndpoints, BatchReadAllEndpoints, \
    BatchReadEndpoints, BatchWriteEndpoints
from mytunes._models.api.items import HasAlbumEndpoints, HasArtistEndpoints, HasTrackEndpoints
from mytunes._models.api.playlist import HasPlaylistEndpoints, PlaylistLibraryEndpoints, PlaylistReadWriteEndpoints
from mytunes._models.collection import SyncRemoteResult
from mytunes._models.collection._sync import SYNC_TYPE, get_sync_message, get_sync_items
from mytunes._models.collection.library import MutableLibrary
from mytunes._models.collection.library._remote._base import RemoteLibrary, RemoteLibraryDump, RemotePlaylistDump
from mytunes._models.collection.playlist import RemoteMutablePlaylist, RemotePlaylist
from mytunes._models.item.album import RemoteAlbum
from mytunes._models.item.artist import RemoteArtist
from mytunes._models.item.genre import RemoteGenre
from mytunes._models.item.track import RemoteTrack
from mytunes._models.item.user import RemoteUser
from mytunes._models.properties.uri import HasURI, URI
from mytunes.exception import MyTunesTypeError
from mytunes.processors.filters.compare import ComparerFilter


class RemoteMutableLibrary[
    API: RemoteAPI,
    TT: RemoteTrack,
    PT: RemotePlaylist,
    RT: RemoteArtist,
    AT: RemoteAlbum,
    GT: RemoteGenre,
    UT: RemoteUser
](
    MutableLibrary[UT, TT, UT, PT], RemoteLibrary[API, TT, PT, RT, AT, GT, UT]
):
    sync_filter: ComparerFilter | None = Field(
        description=(
            "The filter to apply when syncing items to the library. "
            "Only items matching the filter will be added when syncing."
        ),
        default=None,
        repr=False,
    )

    ###########################################################################
    ## Add library items
    ###########################################################################
    @IsRemoteService._validate_api(
        "track",
        None,
        (None, HasTrackEndpoints, "{type} endpoints"),
        ("tracks", BatchReadEndpoints, "reading data for {type}s"),
        ("tracks", HasLibraryEndpoints, "library {type}s endpoints"),
        ("tracks.library", BatchWriteEndpoints, "writing data for library {type}s"),
    )
    async def add_tracks(self, uris: Sequence[URI | HasURI]) -> None:
        """Add library tracks to the library."""
        api: HasTrackEndpoints[BatchReadEndpoints | HasLibraryEndpoints[BatchWriteEndpoints]] = self.api
        items = await self._add_library_items(items=uris, items_type="tracks", api=api.tracks)
        self.tracks.extend(items)

    @IsRemoteService._validate_api(
        "artist",
        None,
        (None, HasArtistEndpoints, "{type} endpoints"),
        ("artists", BatchReadEndpoints, "reading data for {type}s"),
        ("artists", HasLibraryEndpoints, "library {type}s endpoints"),
        ("artists.library", BatchWriteEndpoints, "writing data for library {type}s"),
    )
    async def add_artists(self, uris: Sequence[RT | HasURI]) -> None:
        """Add library artists to the library."""
        api: HasArtistEndpoints[BatchReadEndpoints | HasLibraryEndpoints[BatchWriteEndpoints]] = self.api
        items = await self._add_library_items(items=uris, items_type="artists", api=api.artists)
        self.artists.extend(items)

    @IsRemoteService._validate_api(
        "album",
        None,
        (None, HasAlbumEndpoints, "{type} endpoints"),
        ("albums", BatchReadEndpoints, "reading data for {type}s"),
        ("albums", HasLibraryEndpoints, "library {type}s endpoints"),
        ("albums.library", BatchWriteEndpoints, "writing data for library {type}s"),
    )
    async def add_albums(self, uris: Sequence[RT | HasURI]) -> None:
        """Add library albums to the library."""
        api: HasAlbumEndpoints[BatchReadEndpoints | HasLibraryEndpoints[BatchWriteEndpoints]] = self.api
        items = await self._add_library_items(items=uris, items_type="albums", api=api.albums)
        self.albums.extend(items)

    async def _add_library_items(
            self,
            items: Sequence[URI | HasURI],
            items_type: str,
            api: BatchReadEndpoints | HasLibraryEndpoints[BatchWriteEndpoints],
    ) -> list:
        uris: list[URI] = []
        for item in items:
            match item:
                case URI() as uri:
                    # noinspection PyTypeChecker
                    uris.append(uri)
                case HasURI() as it if it.has_uri:
                    # noinspection PyTypeChecker
                    uris.append(it.uri)
                case _:
                    raise MyTunesTypeError(f"Unrecognised URI type: {type(item).__name__!r}")

        message = f"Adding {len(items)} {items_type} to {self._log_name} library"
        self._logger.info(message, header=1)

        count = await api.library.add_many(items)
        return await api.get_many(items) if count > 0 else []

    ###########################################################################
    ## Sync
    ###########################################################################
    async def sync(self, kind: SYNC_TYPE = "new", dry_run: bool = False) -> dict[str, SyncRemoteResult]:
        """
        Synchronise all items in this library with the remote service.

        Sync options:
            * 'new': Do not clear any items from the remote service and only add new items.
            * 'refresh': Clear all items from the remote service first, then add all items.
            * 'sync': Clear all items not currently on the remote service, then add all items
                from this library not currently in the remote service.

        :param kind: Sync option for the remote service. See description.
        :param dry_run: Run function, but do not modify the remote service at all.
        :return: Map of item type to the sync result.
        """
        self._logger.info(f"Synchronising {self._log_name} library", header=1)

        with self._progress:
            results = await self.sync_playlists(kind=kind, dry_run=dry_run)
            results["TRACKS"] = await self.sync_tracks(kind=kind, dry_run=dry_run)
            results["ARTISTS"] = await self.sync_artists(kind=kind, dry_run=dry_run)
            results["ALBUMS"] = await self.sync_albums(kind=kind, dry_run=dry_run)

        self.log_sync_results(results)
        return results

    def log_sync_results(self, results: Mapping[str, SyncRemoteResult]) -> None:
        """Log stats from the given sync playlist results"""
        header = f"{self._log_name.upper()} SYNC RESULTS"
        table = SyncRemoteResult.generate_table(results=results, header=header)

        self._logger.stat(table)

    ###########################################################################
    ## Sync library items
    ###########################################################################
    @IsRemoteService._validate_api(
        "track",
        None,
        (None, HasTrackEndpoints, "{type} endpoints"),
        ("tracks", HasLibraryEndpoints, "library {type}s endpoints"),
        ("tracks.library", BatchReadAllEndpoints, "reading data for library {type}s"),
        ("tracks.library", BatchWriteEndpoints, "writing data for library {type}s"),
    )
    async def sync_tracks(self, kind: SYNC_TYPE = "new", dry_run: bool = False) -> SyncRemoteResult:
        """
        Synchronise the current library track's with the remote service.

        Sync options:
            * 'new': Do not clear any library tracks from the remote service and only add new tracks.
            * 'refresh': Clear all library tracks from the remote service first, then add all tracks.
            * 'sync': Clear all library tracks not currently on the remote service, then add all tracks
                from this library not currently in the remote service.

        :param kind: Sync option for the remote service. See description.
        :param dry_run: Run function, but do not modify the remote service at all.
        :return: The sync result.
        """
        api: HasTrackEndpoints[HasLibraryEndpoints[BatchReadAllEndpoints | BatchWriteEndpoints]] = self.api
        return await self._sync_library_items(
            items=self.tracks, items_type="tracks", kind=kind, api=api.tracks, dry_run=dry_run
        )

    @IsRemoteService._validate_api(
        "artist",
        None,
        (None, HasArtistEndpoints, "{type} endpoints"),
        ("artists", HasLibraryEndpoints, "library {type}s endpoints"),
        ("artists.library", BatchReadAllEndpoints, "reading data for library {type}s"),
        ("artists.library", BatchWriteEndpoints, "writing data for library {type}s"),
    )
    async def sync_artists(self, kind: SYNC_TYPE = "new", dry_run: bool = False) -> SyncRemoteResult:
        """
        Synchronise the current library artist's with the remote service.

        Sync options:
            * 'new': Do not clear any library artists from the remote service and only add new artists.
            * 'refresh': Clear all library artists from the remote service first, then add all artists.
            * 'sync': Clear all library artists not currently on the remote service, then add all artists
                from this library not currently in the remote service.

        :param kind: Sync option for the remote service. See description.
        :param dry_run: Run function, but do not modify the remote service at all.
        :return: The sync result.
        """
        api: HasArtistEndpoints[HasLibraryEndpoints[BatchReadAllEndpoints | BatchWriteEndpoints]] = self.api
        return await self._sync_library_items(
            items=self.artists, items_type="artists", kind=kind, api=api.artists, dry_run=dry_run
        )

    @IsRemoteService._validate_api(
        "album",
        None,
        (None, HasAlbumEndpoints, "{type} endpoints"),
        ("albums", HasLibraryEndpoints, "library {type}s endpoints"),
        ("albums.library", BatchReadAllEndpoints, "reading data for library {type}s"),
        ("albums.library", BatchWriteEndpoints, "writing data for library {type}s"),
    )
    async def sync_albums(self, kind: SYNC_TYPE = "new", dry_run: bool = False) -> SyncRemoteResult:
        """
        Synchronise the current library album's with the remote service.

        Sync options:
            * 'new': Do not clear any library albums from the remote service and only add new albums.
            * 'refresh': Clear all library albums from the remote service first, then add all albums.
            * 'sync': Clear all library albums not currently on the remote service, then add all albums
                from this library not currently in the remote service.

        :param kind: Sync option for the remote service. See description.
        :param dry_run: Run function, but do not modify the remote service at all.
        :return: The sync result.
        """
        api: HasAlbumEndpoints[HasLibraryEndpoints[BatchReadAllEndpoints | BatchWriteEndpoints]] = self.api
        return await self._sync_library_items(
            items=self.albums, items_type="albums", kind=kind, api=api.albums, dry_run=dry_run
        )

    async def _sync_library_items(
            self,
            items: Collection[HasURI],
            items_type: str,
            kind: SYNC_TYPE,
            api: HasLibraryEndpoints[BatchReadAllEndpoints | BatchWriteEndpoints],
            dry_run: bool,
    ) -> SyncRemoteResult:
        """Run a sync of the given type by calling the given add and remove functions with the appropriate items."""
        message_context = get_sync_message(kind, item_type=items_type, from_type="from the library")
        message = f"Synchronising {len(items)} {items_type} on {self._log_name} library: {message_context}"
        self._logger.info(message, header=1)

        items = self._filter_items(items, items_type=items_type)
        initial = [item.uri for item in items if item.uri]
        remote = await api.library.get_all()
        add, remove, unchanged = get_sync_items(kind, initial=initial, remote=remote)

        removed = await api.library.remove_many(remove) if not dry_run else len(remove)
        added = await api.library.add_many(add) if not dry_run else len(add)

        return SyncRemoteResult(
            start=len(remote),
            added=added,
            removed=removed,
            unchanged=len(unchanged),
            difference=added - removed,
            final=len(remote) + added - removed
        )

    def _filter_items[T: Collection](self, items: T, items_type: str) -> T:
        """Filter the given items using this library's sync filter if given."""
        if self.sync_filter is None:
            return items

        initial_count = len(items)
        filtered_items = self.sync_filter.apply(items)
        difference = len(filtered_items) - initial_count
        if difference:
            message = colored(f"Filtered out {difference} {items_type}.", "dark_gray", attrs=["dark"])
            self._logger.info(message, header=3)

        return items

    ###########################################################################
    ## Create/Sync Playlists
    ###########################################################################
    @IsRemoteService._validate_api(
        "playlist",
        None,
        (None, HasPlaylistEndpoints, "{type} endpoints"),
        ("playlists", HasLibraryEndpoints, "library {type}s endpoints"),
        ("playlists.library", PlaylistLibraryEndpoints, "writing data for library {type}s"),
    )
    async def create_playlist(self, name: str, **kwargs) -> PT | None:
        """Create a new playlist with the given name and return it."""
        api: HasPlaylistEndpoints[HasLibraryEndpoints[PlaylistLibraryEndpoints]] = self.api

        if (playlist := next((pl for pl in self.playlists.unique if pl.name == name), None)) is not None:
            self._logger.warning(f"Playlist with name {name!r} already exists in {self._log_name} library.")
            return playlist

        self._logger.info(f"Creating playlist {name!r} on {self._log_name} library", header=2)
        playlist = await api.playlists.library.create(name=name, **kwargs)
        self.playlists.add(playlist)

        return playlist

    @IsRemoteService._validate_api(
        "playlist",
        dict,
        (None, HasPlaylistEndpoints, "{type} endpoints"),
        ("playlists", PlaylistReadWriteEndpoints, "writing data for {type}s"),
        ("playlists", HasLibraryEndpoints, "library {type}s endpoints"),
        ("playlists.library", PlaylistLibraryEndpoints, "writing data for library {type}s"),
    )
    async def sync_playlists(self, kind: SYNC_TYPE = "new", dry_run: bool = False) -> dict[str, SyncRemoteResult]:
        """
        Synchronise the items of playlists in this library with the remote service.

        Clear options:
            * 'new': Do not clear any items from the remote playlist and only add any tracks
                from this playlist object not currently in the remote playlist.
            * 'refresh': Clear all items from the remote playlist first, then add all items from this playlist object.
            * 'sync': Clear all items not currently in this object's items list, then add all tracks
                from this playlist object not currently in the remote playlist.

        :param kind: Sync option for the remote playlist. See description.
        :param dry_run: Run function, but do not modify the remote playlists at all.
        :return: Map of playlist name to the sync result.
        """
        api: HasPlaylistEndpoints[
            PlaylistReadWriteEndpoints | HasLibraryEndpoints[PlaylistLibraryEndpoints]
        ] = self.api

        playlists = list(filter(lambda pl: isinstance(pl, RemoteMutablePlaylist), self.playlists.unique))

        message_context = get_sync_message(kind, item_type="items", from_type=f"from each {self.source} playlist")
        message = f"Synchronising {len(playlists)} playlists on {self._log_name} library: {message_context}"
        self._logger.info(message, header=1)

        async def _sync_playlist[T: RemoteMutablePlaylist](pl: T) -> tuple[str, SyncRemoteResult]:
            async with self.concurrency:
                remote: T = await api.playlists.library.get_or_create(pl.name)
                remote.tracks.replace(pl.tracks)

                properties = await remote.sync_properties(api, dry_run=dry_run)
                result = await remote.sync_items(api, kind=kind, items_filter=self.sync_filter, dry_run=dry_run)

                return pl.name, result.model_copy(update=dict(properties=properties))

        task_id = self._progress.add_task(
            description=f"Synchronising {self.source.title()} playlists", total=len(playlists),
        )
        results = await self._run_tasks_async(map(_sync_playlist, playlists), task_id=task_id)
        return dict(results)

    ###########################################################################
    ## Restore library items
    ###########################################################################
    @validate_call
    async def restore(self, backup: RemoteLibraryDump[URI], dry_run: bool = False) -> dict[str, SyncRemoteResult]:
        """
        Restore library from a backup.

        :param backup: Backup data to restore.
        :param dry_run: Run function, but do not modify the remote service at all.
        :return: The results of the restore as a mapping of item type to either a sync result
            or a mapping of playlist name to a sync result.
        """
        results: dict[str, SyncRemoteResult] = {}

        with self._progress:
            if "tracks" in backup:
                results["tracks"] = await self.restore_tracks(backup["tracks"], dry_run=dry_run)
            if "artists" in backup:
                results["artists"] = await self.restore_artists(backup["artists"], dry_run=dry_run)
            if "albums" in backup:
                results["albums"] = await self.restore_albums(backup["albums"], dry_run=dry_run)
            if "playlists" in backup:
                results |= await self.restore_playlists(backup["playlists"], dry_run=dry_run)

        self.log_sync_results(results)
        return results

    @staticmethod
    def _extract_uris_from_backup(backup: Any, key: Literal["tracks", "artists", "albums"]) -> tuple[str | URI, ...]:
        if isinstance(backup, Mapping) and key in backup:
            backup = backup[key]

        match backup:
            case Mapping() as items if all(isinstance(item, Mapping) and "uri" in item for item in items.values()):
                return tuple(item["uri"] for item in items.values())
            case Mapping() as items:  # assume keys are URIs if values are not dicts with "uri" keys
                return tuple(map(str, items.keys()))
            case Collection() as items if all(isinstance(item, Mapping) and "uri" in item for item in items):
                return tuple(item["uri"] for item in items)
            case Collection() as items if not isinstance(items, Mapping):  # assume items are URIs
                return tuple(map(str, items))
            case _:
                raise MyTunesTypeError(f"Unrecognised backup dump format: {type(backup).__name__!r}.")

    @staticmethod
    def _extract_tracks_from_backup(backup: Any) -> tuple[str | URI, ...]:
        return RemoteMutableLibrary._extract_uris_from_backup(backup, "tracks")

    @IsRemoteService._validate_api(
        "track",
        None,
        (None, HasTrackEndpoints, "{type} endpoints"),
        ("tracks", BatchReadEndpoints, "reading data for {type}s"),
        ("tracks", HasLibraryEndpoints, "library {type}s endpoints"),
        ("tracks.library", BatchReadAllEndpoints, "reading data for library {type}s"),
        ("tracks.library", BatchWriteEndpoints, "writing data for library {type}s"),
    )
    @validate_call
    async def restore_tracks(
            self,
            uris: Annotated[Sequence[str | URI], BeforeValidator(_extract_tracks_from_backup)],
            dry_run: bool = False
    ) -> SyncRemoteResult | None:
        """
        Restore library tracks from a backup dump.
        This function updates the remote service and reloads this library's tracks after restoring.

        Tracks may be in the form of either:
            * A sequence of track URIs
            * A sequence of dictionaries where dictionary is ``{<Dump of track data>}``
            * A mapping of ``{<URI>: {<Dump of track data>}}``
            * A mapping of ``{"tracks": {<URI>: {<Dump of track data>}}}``

        :param uris: Tracks data. See description for accepted formats.
        :param dry_run: Run function, but do not modify the remote service at all.
        :return: The count of library tracks on the remote service after the sync.
        """
        api: HasTrackEndpoints[
            BatchReadEndpoints | HasLibraryEndpoints[BatchReadAllEndpoints | BatchWriteEndpoints]
        ] = self.api

        self._logger.info(f"Restoring {len(uris)} library tracks on {self._log_name} library", header=2)

        self.tracks[:] = await api.tracks.get_many(uris)
        return await self.sync_tracks(kind="refresh", dry_run=dry_run)

    @staticmethod
    def _extract_artists_from_backup(backup: Any) -> tuple[str | URI, ...]:
        return RemoteMutableLibrary._extract_uris_from_backup(backup, "artists")

    @IsRemoteService._validate_api(
        "artist",
        None,
        (None, HasArtistEndpoints, "{type} endpoints"),
        ("artists", BatchReadEndpoints, "reading data for {type}s"),
        ("artists", HasLibraryEndpoints, "library {type}s endpoints"),
        ("artists.library", BatchReadAllEndpoints, "reading data for library {type}s"),
        ("artists.library", BatchWriteEndpoints, "writing data for library {type}s"),
    )
    @validate_call
    async def restore_artists(
            self,
            uris: Annotated[Sequence[str | URI], BeforeValidator(_extract_artists_from_backup)],
            dry_run: bool = False
    ) -> SyncRemoteResult | None:
        """
        Restore library artists from a backup dump.
        This function updates the remote service and reloads this library's artists after restoring.

        Artists may be in the form of either:
            * A sequence of Artist URIs
            * A sequence of dictionaries where dictionary is ``{<Dump of artist data>}``
            * A mapping of ``{<URI>: {<Dump of artist data>}}``
            * A mapping of ``{"artists": {<URI>: {<Dump of artist data>}}}``

        :param uris: Artists data. See description for accepted formats.
        :param dry_run: Run function, but do not modify the remote service at all.
        :return: The count of library artists on the remote service after the sync.
        """
        api: HasArtistEndpoints[
            BatchReadEndpoints | HasLibraryEndpoints[BatchReadAllEndpoints | BatchWriteEndpoints]
        ] = self.api

        self._logger.info(f"Restoring {len(uris)} library artists on {self._log_name} library", header=2)

        self.artists[:] = await api.artists.get_many(uris)
        return await self.sync_artists(kind="refresh", dry_run=dry_run)

    @staticmethod
    def _extract_albums_from_backup(backup: Any) -> tuple[str | URI, ...]:
        return RemoteMutableLibrary._extract_uris_from_backup(backup, "albums")

    @IsRemoteService._validate_api(
        "album",
        None,
        (None, HasAlbumEndpoints, "{type} endpoints"),
        ("albums", BatchReadEndpoints, "reading data for {type}s"),
        ("albums", HasLibraryEndpoints, "library {type}s endpoints"),
        ("albums.library", BatchReadAllEndpoints, "reading data for library {type}s"),
        ("albums.library", BatchWriteEndpoints, "writing data for library {type}s"),
    )
    @validate_call
    async def restore_albums(
            self,
            uris: Annotated[Sequence[str | URI], BeforeValidator(_extract_albums_from_backup)],
            dry_run: bool = False
    ) -> SyncRemoteResult | None:
        """
        Restore library albums from a backup dump.
        This function updates the remote service and reloads this library's albums after restoring.

        Albums may be in the form of either:
            * A sequence of Album URIs
            * A sequence of dictionaries where dictionary is ``{<Dump of album data>}``
            * A mapping of ``{<URI>: {<Dump of album data>}}``
            * A mapping of ``{"albums": {<URI>: {<Dump of album data>}}}``

        :param uris: Albums data. See description for accepted formats.
        :param dry_run: Run function, but do not modify the remote service at all.
        :return: The count of library albums on the remote service after the sync.
        """
        api: HasAlbumEndpoints[
            BatchReadEndpoints | HasLibraryEndpoints[BatchReadAllEndpoints | BatchWriteEndpoints]
        ] = self.api

        self._logger.info(f"Restoring {len(uris)} library albums on {self._log_name} library", header=2)

        self.albums[:] = await api.albums.get_many(uris)
        return await self.sync_albums(kind="refresh", dry_run=dry_run)

    ###########################################################################
    ## Restore playlists
    ###########################################################################
    @staticmethod
    def _extract_playlists_from_backup(backup: Any, key: str = "playlists") -> tuple[RemotePlaylistDump[URI], ...]:
        if isinstance(backup, Mapping) and key in backup:
            backup = backup[key]

        def _has_expected_keys(pl: Any) -> bool:
            return isinstance(pl, Mapping) and all((
                "name" in pl,
                "uri" in pl,
                "items" in pl,
            ))

        match backup:
            case Mapping() as playlists if all(map(_has_expected_keys, playlists.values())):
                playlists = playlists.values()
            case Collection() as playlists if all(map(_has_expected_keys, playlists)):
                pass
            case _:
                raise MyTunesTypeError(f"Unrecognised backup dump format: {type(backup).__name__!r}.")

        # noinspection PyTypeChecker
        return tuple(map(dict, playlists))

    @IsRemoteService._validate_api(
        "playlist",
        dict,
        (None, HasPlaylistEndpoints, "{type} endpoints"),
        ("playlists", PlaylistReadWriteEndpoints, "writing data for {type}s"),
        ("playlists", HasLibraryEndpoints, "library {type}s endpoints"),
        ("playlists.library", PlaylistLibraryEndpoints, "writing data for library {type}s"),
        (None, HasTrackEndpoints, "track endpoints"),
        ("tracks", BatchReadEndpoints, "reading data for tracks"),
    )
    @validate_call
    async def restore_playlists(
            self,
            playlists: Annotated[Sequence[RemotePlaylistDump[URI]], BeforeValidator(_extract_playlists_from_backup)],
            dry_run: bool = False,
    ) -> dict[str, SyncRemoteResult]:
        """
        Restore playlists from a backup dump.
        This function updates the remote service and reloads this library's playlists after restoring.

        Playlists may be in the form of either:
            * A sequence of dictionaries where dictionary is ``{<Dump of playlist data>}``
            * A mapping of ``{<URI>: {<Dump of playlist data>}}``
            * A mapping of lists ``{"playlists": [{<Dump of track data>}]}``

        :param playlists: Tracks data. See description for accepted formats.
        :param dry_run: Run function, but do not modify the remote service at all.
        :return: The count of library tracks on the remote service after the sync.
        """
        self._logger.info(f"Restoring {len(playlists)} playlists on {self._log_name} library", header=2)

        def _restore_playlist(dump: dict[str, Any]):
            name = dump.pop("name")
            uri = dump.pop("uri")
            items = dump.pop("items")
            return self._restore_playlist(uri=uri, name=name, items=items, properties=dump, dry_run=dry_run)

        task_id = self._progress.add_task(
            description=f"Restoring {self.source.title()} playlists", total=len(playlists),
        )
        results = await self._run_tasks_async(map(_restore_playlist, playlists), task_id=task_id)

        await self.load_playlists()
        return dict(results)

    async def _restore_playlist(
            self,
            uri: str | URI,
            name: str,
            items: Sequence[str | URI],
            properties: Mapping[str, Any],
            dry_run: bool = False,
    ) -> tuple[str, SyncRemoteResult] | None:
        api: (
            HasPlaylistEndpoints[PlaylistReadWriteEndpoints | HasLibraryEndpoints[PlaylistLibraryEndpoints]] |
            HasTrackEndpoints[BatchReadEndpoints]
        ) = self.api

        async with self.concurrency:
            try:
                playlist = await api.playlists.get(uri)
            except ResponseError as exc:
                if not dry_run and exc.response.status == 404:
                    self._logger.warning(
                        f"Playlist with name {name!r} does not exist on the remote service. "
                        "Creating a new playlist."
                    )
                    playlist = await api.playlists.library.create(name=name, **properties)
                else:
                    item_count = len(items)
                    return name, SyncRemoteResult(
                        start=0,
                        added=item_count,
                        removed=0,
                        unchanged=0,
                        difference=item_count,
                        final=item_count,
                    )

            if not isinstance(playlist, RemoteMutablePlaylist):
                self._logger.warning(f"Playlist {playlist.name!r} could not be updated as it is not writeable.")
                return

            playlist.tracks.replace(await api.tracks.get_many(items))

            return playlist.name, await playlist.sync_items(api=api, kind="refresh", dry_run=dry_run)
