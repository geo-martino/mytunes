import functools
from collections.abc import Collection, Mapping, Sequence
from typing import Any, Literal, Annotated

from aiorequestful.response.exception import ResponseError
from pydantic import Field, validate_call, BeforeValidator
from termcolor import colored

from musify.exception import MusifyTypeError
from musify.models.api import RemoteAPI, IsRemoteService, HasSavedEndpoints, ReadSavedEndpoints, WriteSavedEndpoints, \
    ReadItemsEndpoints
from musify.models.api.album import HasAlbumEndpoints, AlbumReadSavedEndpoints, AlbumWriteSavedEndpoints, \
    AlbumReadItemsEndpoints
from musify.models.api.artist import HasArtistEndpoints, ArtistReadSavedEndpoints, ArtistWriteSavedEndpoints, \
    ArtistReadItemsEndpoints
from musify.models.api.playlist import HasPlaylistEndpoints, PlaylistReadWriteSavedEndpoints, PlaylistReadWriteEndpoints
from musify.models.api.track import HasTrackEndpoints, TrackReadSavedEndpoints, TrackWriteSavedEndpoints, \
    TrackReadItemsEndpoints
from musify.models.collection import SyncRemoteResult
from musify.models.collection._sync import SYNC_TYPE, get_sync_message, get_sync_items
from musify.models.collection.library import MutableLibrary
from musify.models.collection.library._remote._base import RemoteLibrary
from musify.models.collection.playlist import RemoteMutablePlaylist, RemotePlaylist
from musify.models.item.album import RemoteAlbum
from musify.models.item.artist import RemoteArtist
from musify.models.item.genre import RemoteGenre
from musify.models.item.track import RemoteTrack
from musify.models.properties.uri import HasURI, URI
from musify.models.user import RemoteUser
from musify.processors.filters.compare import ComparerFilter


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
    )

    ###########################################################################
    ## Add saved items
    ###########################################################################
    @IsRemoteService._validate_api(
        "track",
        None,
        (None, HasTrackEndpoints, "{type} endpoints"),
        ("tracks", TrackReadItemsEndpoints, "reading data for {type}s"),
        ("tracks", HasSavedEndpoints, "saved {type}s endpoints"),
        ("tracks.saved", TrackWriteSavedEndpoints, "writing data for saved {type}s"),
    )
    async def add_tracks(self, uris: Sequence[UT | HasURI]) -> None:
        """Add saved tracks to the library."""
        api: HasTrackEndpoints[TrackReadItemsEndpoints | HasSavedEndpoints[TrackWriteSavedEndpoints]] = self.api
        items = await self._add_saved_items(items=uris, items_type="tracks", api=api.tracks)
        self.tracks.extend(items)

    @IsRemoteService._validate_api(
        "artist",
        None,
        (None, HasArtistEndpoints, "{type} endpoints"),
        ("artists", ArtistReadItemsEndpoints, "reading data for {type}s"),
        ("artists", HasSavedEndpoints, "saved {type}s endpoints"),
        ("artists.saved", ArtistWriteSavedEndpoints, "writing data for saved {type}s"),
    )
    async def add_artists(self, uris: Sequence[RT | HasURI]) -> None:
        """Add saved artists to the library."""
        api: HasArtistEndpoints[ArtistReadItemsEndpoints | HasSavedEndpoints[ArtistWriteSavedEndpoints]] = self.api
        items = await self._add_saved_items(items=uris, items_type="artists", api=api.artists)
        self.artists.extend(items)

    @IsRemoteService._validate_api(
        "album",
        None,
        (None, HasAlbumEndpoints, "{type} endpoints"),
        ("albums", AlbumReadItemsEndpoints, "reading data for {type}s"),
        ("albums", HasSavedEndpoints, "saved {type}s endpoints"),
        ("albums.saved", AlbumWriteSavedEndpoints, "writing data for saved {type}s"),
    )
    async def add_albums(self, uris: Sequence[RT | HasURI]) -> None:
        """Add saved albums to the library."""
        api: HasAlbumEndpoints[AlbumReadItemsEndpoints | HasSavedEndpoints[AlbumWriteSavedEndpoints]] = self.api
        items = await self._add_saved_items(items=uris, items_type="albums", api=api.albums)
        self.albums.extend(items)

    async def _add_saved_items(
            self,
            items: Sequence[UT | HasURI],
            items_type: str,
            api: ReadItemsEndpoints | HasSavedEndpoints[WriteSavedEndpoints],
    ) -> list:
        uris: list[UT] = []
        for item in items:
            match item:
                case URI() as uri:
                    # noinspection PyTypeChecker
                    uris.append(uri)
                case HasURI() as it if it.has_uri:
                    # noinspection PyTypeChecker
                    uris.append(it.uri)
                case _:
                    raise MusifyTypeError(f"Unrecognised URI type: {type(item).__name__!r}")

        message = f"Adding {len(items)} {items_type} to {self._log_name} library"
        self.logger.info(message, header=1)

        count = await api.saved.add_many(items)
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
        self.logger.info(f"Synchronising {self._log_name} library", header=1)

        with self.logger:
            results = await self.sync_playlist_items(kind=kind, dry_run=dry_run)
            results["TRACKS"] = await self.sync_tracks(kind=kind, dry_run=dry_run)
            results["ARTISTS"] = await self.sync_artists(kind=kind, dry_run=dry_run)
            results["ALBUMS"] = await self.sync_albums(kind=kind, dry_run=dry_run)

        self.log_sync_results(results)
        return results

    def log_sync_results(self, results: Mapping[str, SyncRemoteResult]) -> None:
        """Log stats from the given sync playlist results"""
        header = f"{self._log_name.upper()} SYNC RESULTS"
        table = SyncRemoteResult.generate_table(results=results, header=header)

        self.logger.stat(table)

    ###########################################################################
    ## Sync saved items
    ###########################################################################
    @IsRemoteService._validate_api(
        "track",
        None,
        (None, HasTrackEndpoints, "{type} endpoints"),
        ("tracks", HasSavedEndpoints, "saved {type}s endpoints"),
        ("tracks.saved", TrackReadSavedEndpoints, "reading data for saved {type}s"),
        ("tracks.saved", TrackWriteSavedEndpoints, "writing data for saved {type}s"),
    )
    async def sync_tracks(self, kind: SYNC_TYPE = "new", dry_run: bool = False) -> SyncRemoteResult:
        """
        Synchronise the current saved track's with the remote service.

        Sync options:
            * 'new': Do not clear any saved tracks from the remote service and only add new tracks.
            * 'refresh': Clear all saved tracks from the remote service first, then add all tracks.
            * 'sync': Clear all saved tracks not currently on the remote service, then add all tracks
                from this library not currently in the remote service.

        :param kind: Sync option for the remote service. See description.
        :param dry_run: Run function, but do not modify the remote service at all.
        :return: The sync result.
        """
        api: HasTrackEndpoints[HasSavedEndpoints[TrackReadSavedEndpoints | TrackWriteSavedEndpoints]] = self.api
        return await self._sync_saved_items(
            items=self.tracks, items_type="tracks", kind=kind, api=api.tracks, dry_run=dry_run
        )

    @IsRemoteService._validate_api(
        "artist",
        None,
        (None, HasArtistEndpoints, "{type} endpoints"),
        ("artists", HasSavedEndpoints, "saved {type}s endpoints"),
        ("artists.saved", ArtistReadSavedEndpoints, "reading data for saved {type}s"),
        ("artists.saved", ArtistWriteSavedEndpoints, "writing data for saved {type}s"),
    )
    async def sync_artists(self, kind: SYNC_TYPE = "new", dry_run: bool = False) -> SyncRemoteResult:
        """
        Synchronise the current saved artist's with the remote service.

        Sync options:
            * 'new': Do not clear any saved artists from the remote service and only add new artists.
            * 'refresh': Clear all saved artists from the remote service first, then add all artists.
            * 'sync': Clear all saved artists not currently on the remote service, then add all artists
                from this library not currently in the remote service.

        :param kind: Sync option for the remote service. See description.
        :param dry_run: Run function, but do not modify the remote service at all.
        :return: The sync result.
        """
        api: HasArtistEndpoints[HasSavedEndpoints[ArtistReadSavedEndpoints | ArtistWriteSavedEndpoints]] = self.api
        return await self._sync_saved_items(
            items=self.artists, items_type="artists", kind=kind, api=api.artists, dry_run=dry_run
        )

    @IsRemoteService._validate_api(
        "album",
        None,
        (None, HasAlbumEndpoints, "{type} endpoints"),
        ("albums", HasSavedEndpoints, "saved {type}s endpoints"),
        ("albums.saved", AlbumReadSavedEndpoints, "reading data for saved {type}s"),
        ("albums.saved", AlbumWriteSavedEndpoints, "writing data for saved {type}s"),
    )
    async def sync_albums(self, kind: SYNC_TYPE = "new", dry_run: bool = False) -> SyncRemoteResult:
        """
        Synchronise the current saved album's with the remote service.

        Sync options:
            * 'new': Do not clear any saved albums from the remote service and only add new albums.
            * 'refresh': Clear all saved albums from the remote service first, then add all albums.
            * 'sync': Clear all saved albums not currently on the remote service, then add all albums
                from this library not currently in the remote service.

        :param kind: Sync option for the remote service. See description.
        :param dry_run: Run function, but do not modify the remote service at all.
        :return: The sync result.
        """
        api: HasAlbumEndpoints[HasSavedEndpoints[AlbumReadSavedEndpoints | AlbumWriteSavedEndpoints]] = self.api
        return await self._sync_saved_items(
            items=self.albums, items_type="albums", kind=kind, api=api.albums, dry_run=dry_run
        )

    async def _sync_saved_items(
            self,
            items: Collection[HasURI],
            items_type: str,
            kind: SYNC_TYPE,
            api: HasSavedEndpoints[ReadSavedEndpoints | WriteSavedEndpoints],
            dry_run: bool,
    ) -> SyncRemoteResult:
        """Run a sync of the given type by calling the given add and remove functions with the appropriate items."""
        message_context = get_sync_message(kind, item_type=items_type, from_type="from the library")
        message = f"Synchronising {len(items)} {items_type} on {self._log_name} library: {message_context}"
        self.logger.info(message, header=1)

        items = self._filter_items(items, items_type=items_type)
        initial = [item.uri for item in items if item.uri]
        remote = await api.saved.get_all()
        add, remove, unchanged = get_sync_items(kind, initial=initial, remote=remote)

        removed = await api.saved.remove_many(remove) if not dry_run else len(remove)
        added = await api.saved.add_many(add) if not dry_run else len(add)

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
            self.logger.info(message, header=3)

        return items

    ###########################################################################
    ## Create/Sync Playlists
    ###########################################################################
    @IsRemoteService._validate_api(
        "playlist",
        None,
        (None, HasPlaylistEndpoints, "{type} endpoints"),
        ("playlists", HasSavedEndpoints, "saved {type}s endpoints"),
        ("playlists.saved", PlaylistReadWriteSavedEndpoints, "writing data for saved {type}s"),
    )
    async def create_playlist(self, name: str, **kwargs) -> PT | None:
        """Create a new playlist with the given name and return it."""
        api: HasPlaylistEndpoints[HasSavedEndpoints[PlaylistReadWriteSavedEndpoints]] = self.api

        if (playlist := next((pl for pl in self.playlists.unique if pl.name == name), None)) is not None:
            self.logger.warning(f"Playlist with name {name!r} already exists in {self._log_name} library.")
            return playlist

        self.logger.info(f"Creating playlist {name!r} on {self._log_name} library", header=2)
        playlist = await api.playlists.saved.create(name=name, **kwargs)
        self.playlists.add(playlist)

        return playlist

    @IsRemoteService._validate_api(
        "playlist",
        dict,
        (None, HasPlaylistEndpoints, "{type} endpoints"),
        ("playlists", PlaylistReadWriteEndpoints, "writing data for {type}s"),
        ("playlists", HasSavedEndpoints, "saved {type}s endpoints"),
        ("playlists.saved", PlaylistReadWriteSavedEndpoints, "writing data for saved {type}s"),
    )
    async def sync_playlist_items(self, kind: SYNC_TYPE = "new", dry_run: bool = False) -> dict[str, SyncRemoteResult]:
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
            PlaylistReadWriteEndpoints | HasSavedEndpoints[PlaylistReadWriteSavedEndpoints]
        ] = self.api

        playlists = list(filter(lambda pl: isinstance(pl, RemoteMutablePlaylist), self.playlists.unique))

        message_context = get_sync_message(kind, item_type="items", from_type=f"from each {self.source} playlist")
        message = f"Synchronising {len(playlists)} playlists on {self._log_name} library: {message_context}"
        self.logger.info(message, header=1)

        async def _sync_playlist[T: RemoteMutablePlaylist](pl: T) -> tuple[str, SyncRemoteResult]:
            async with self.concurrency:
                remote: T = await api.playlists.saved.get_or_create(pl.name)
                remote.tracks.replace(pl.tracks)

                properties = await remote.sync_properties(api, dry_run=dry_run)
                result = await remote.sync_items(
                    api=api, kind=kind, items_filter=self.sync_filter, dry_run=dry_run, show_bar=False
                )

                return pl.name, result.model_copy(update=dict(properties=properties))

        task_id = self.logger.progress.add_task(
            description=f"Synchronising {self.source.title()} playlists", total=len(playlists),
        )
        results = await self.logger.run_tasks_async(map(_sync_playlist, playlists), task_id=task_id)
        return dict(results)

    ###########################################################################
    ## Restore saved items
    ###########################################################################
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
                raise MusifyTypeError(f"Unrecognised backup dump format: {type(backup).__name__!r}.")

    @IsRemoteService._validate_api(
        "track",
        None,
        (None, HasTrackEndpoints, "{type} endpoints"),
        ("tracks", TrackReadItemsEndpoints, "reading data for {type}s"),
        ("tracks", HasSavedEndpoints, "saved {type}s endpoints"),
        ("tracks.saved", TrackReadSavedEndpoints, "reading data for saved {type}s"),
        ("tracks.saved", TrackWriteSavedEndpoints, "writing data for saved {type}s"),
    )
    @validate_call
    async def restore_tracks(
            self,
            uris: Annotated[
                Sequence[str | URI],
                BeforeValidator(functools.partial(_extract_uris_from_backup, key="tracks"))
            ],
            dry_run: bool = False
    ) -> SyncRemoteResult | None:
        """
        Restore saved tracks from a backup dump.
        This function updates the remote service and reloads this library's tracks after restoring.

        Tracks may be in the form of either:
            * A sequence of track URIs
            * A sequence of dictionaries where dictionary is ``{<Dump of track data>}``
            * A mapping of ``{<URI>: {<Dump of track data>}}``
            * A mapping of ``{"tracks": {<URI>: {<Dump of track data>}}}``

        :param uris: Tracks data. See description for accepted formats.
        :param dry_run: Run function, but do not modify the remote service at all.
        :return: The count of saved tracks on the remote service after the sync.
        """
        api: HasTrackEndpoints[
            TrackReadItemsEndpoints | HasSavedEndpoints[TrackReadSavedEndpoints | TrackWriteSavedEndpoints]
        ] = self.api

        self.logger.info(f"Restoring {len(uris)} saved tracks on {self._log_name} library", header=2)

        self.tracks[:] = await api.tracks.get_many(uris)
        return await self.sync_tracks(kind="refresh", dry_run=dry_run)

    @IsRemoteService._validate_api(
        "artist",
        None,
        (None, HasArtistEndpoints, "{type} endpoints"),
        ("artists", ArtistReadItemsEndpoints, "reading data for {type}s"),
        ("artists", HasSavedEndpoints, "saved {type}s endpoints"),
        ("artists.saved", ArtistReadSavedEndpoints, "reading data for saved {type}s"),
        ("artists.saved", ArtistWriteSavedEndpoints, "writing data for saved {type}s"),
    )
    @validate_call
    async def restore_artists(
            self,
            uris: Annotated[
                Sequence[str | URI],
                BeforeValidator(functools.partial(_extract_uris_from_backup, key="artists"))
            ],
            dry_run: bool = False
    ) -> SyncRemoteResult | None:
        """
        Restore saved artists from a backup dump.
        This function updates the remote service and reloads this library's artists after restoring.

        Artists may be in the form of either:
            * A sequence of Artist URIs
            * A sequence of dictionaries where dictionary is ``{<Dump of artist data>}``
            * A mapping of ``{<URI>: {<Dump of artist data>}}``
            * A mapping of ``{"artists": {<URI>: {<Dump of artist data>}}}``

        :param uris: Artists data. See description for accepted formats.
        :param dry_run: Run function, but do not modify the remote service at all.
        :return: The count of saved artists on the remote service after the sync.
        """
        api: HasArtistEndpoints[
            ArtistReadItemsEndpoints | HasSavedEndpoints[ArtistReadSavedEndpoints | ArtistWriteSavedEndpoints]
        ] = self.api

        self.logger.info(f"Restoring {len(uris)} saved artists on {self._log_name} library", header=2)

        self.artists[:] = await api.artists.get_many(uris)
        return await self.sync_artists(kind="refresh", dry_run=dry_run)

    @IsRemoteService._validate_api(
        "album",
        None,
        (None, HasAlbumEndpoints, "{type} endpoints"),
        ("albums", AlbumReadItemsEndpoints, "reading data for {type}s"),
        ("albums", HasSavedEndpoints, "saved {type}s endpoints"),
        ("albums.saved", AlbumReadSavedEndpoints, "reading data for saved {type}s"),
        ("albums.saved", AlbumWriteSavedEndpoints, "writing data for saved {type}s"),
    )
    @validate_call
    async def restore_albums(
            self,
            uris: Annotated[
                Sequence[str | URI],
                BeforeValidator(functools.partial(_extract_uris_from_backup, key="albums"))
            ],
            dry_run: bool = False
    ) -> SyncRemoteResult | None:
        """
        Restore saved albums from a backup dump.
        This function updates the remote service and reloads this library's albums after restoring.

        Albums may be in the form of either:
            * A sequence of Album URIs
            * A sequence of dictionaries where dictionary is ``{<Dump of album data>}``
            * A mapping of ``{<URI>: {<Dump of album data>}}``
            * A mapping of ``{"albums": {<URI>: {<Dump of album data>}}}``

        :param uris: Albums data. See description for accepted formats.
        :param dry_run: Run function, but do not modify the remote service at all.
        :return: The count of saved albums on the remote service after the sync.
        """
        api: HasAlbumEndpoints[
            AlbumReadItemsEndpoints | HasSavedEndpoints[AlbumReadSavedEndpoints | AlbumWriteSavedEndpoints]
        ] = self.api

        self.logger.info(f"Restoring {len(uris)} saved albums on {self._log_name} library", header=2)

        self.albums[:] = await api.albums.get_many(uris)
        return await self.sync_albums(kind="refresh", dry_run=dry_run)

    ###########################################################################
    ## Restore playlists
    ###########################################################################
    @staticmethod
    def _extract_playlists_from_backup(
            backup: Any, key: str = "playlists"
    ) -> tuple[tuple[str | URI, dict[str, Any], tuple[str | URI, ...]], ...]:
        if isinstance(backup, Mapping) and key in backup:
            backup = backup[key]

        match backup:
            case Mapping() as playlists if all(isinstance(pl, Mapping) and "uri" in pl for pl in playlists.values()):
                playlists = playlists.values()
            case Collection() as playlists if all(isinstance(pl, Mapping) and "uri" in pl for pl in playlists):
                pass
            case _:
                raise MusifyTypeError(f"Unrecognised backup dump format: {type(backup).__name__!r}.")

        return tuple(
            (pl["uri"], pl, RemoteMutableLibrary._extract_uris_from_backup(pl, "tracks"))
            for pl in playlists
        )

    def restore(
            self, backup: Any, dry_run: bool = False
    ) -> dict[str, SyncRemoteResult] | SyncRemoteResult | None:
        """
        Restore library from a backup.

        :param backup: Backup data to restore.
        :param dry_run: Run function, but do not modify the remote service at all.
        :return: The results of the restore as a mapping of item type to either a sync result
            or a mapping of playlist name to a sync result.
        """
        results: dict[str, SyncRemoteResult] = {}

        with self.logger:
            if "playlists" in backup:
                results |= self.restore_playlists(backup, dry_run=dry_run)
            if "tracks" in backup:
                results |= self.restore_tracks(backup, dry_run=dry_run)
            if "artists" in backup:
                results |= self.restore_artists(backup, dry_run=dry_run)
            if "albums" in backup:
                results |= self.restore_albums(backup, dry_run=dry_run)

        self.log_sync_results(results)
        return results

    # TODO: the typing here is atrocious, fix this
    @IsRemoteService._validate_api(
        "playlist",
        dict,
        (None, HasPlaylistEndpoints, "{type} endpoints"),
        ("playlists", PlaylistReadWriteEndpoints, "writing data for {type}s"),
        ("playlists", HasSavedEndpoints, "saved {type}s endpoints"),
        ("playlists.saved", PlaylistReadWriteSavedEndpoints, "writing data for saved {type}s"),
        (None, HasTrackEndpoints, "track endpoints"),
        ("tracks", TrackReadItemsEndpoints, "reading data for tracks"),
    )
    @validate_call
    async def restore_playlists(
            self,
            playlists: Annotated[
                tuple[tuple[str | URI, dict[str, Any], tuple[str | URI, ...]], ...],
                BeforeValidator(_extract_playlists_from_backup)
            ],
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
        :return: The count of saved tracks on the remote service after the sync.
        """

        self.logger.info(f"Restoring {len(playlists)} playlists on {self._log_name} library", header=2)

        def _restore_playlist(dump):
            return self._restore_playlist(*dump, dry_run=dry_run)

        task_id = self.logger.progress.add_task(
            description=f"Restoring {self.source.title()} playlists", total=len(playlists),
        )
        results = await self.logger.run_tasks_async(map(_restore_playlist, playlists), task_id=task_id)

        await self.load_playlists()
        return dict(results)

    async def _restore_playlist(
            self, uri: URI, dump: Mapping[str, Any], items: list[URI], dry_run: bool = False
    ) -> tuple[str, SyncRemoteResult] | None:
        api: (
            HasPlaylistEndpoints[PlaylistReadWriteEndpoints | HasSavedEndpoints[PlaylistReadWriteSavedEndpoints]] |
            HasTrackEndpoints[TrackReadItemsEndpoints]
        ) = self.api

        async with self.concurrency:
            try:
                playlist = await api.playlists.get(uri.api_url)
            except ResponseError as exc:
                if not dry_run and exc.response.status == 404:
                    self.logger.warning(
                        f"Playlist with name {dump["name"]!r} does not exist on the remote service. "
                        "Creating a new playlist."
                    )
                    playlist = await api.playlists.saved.create(**dump)
                else:
                    item_count = len(items)
                    return dump["name"], SyncRemoteResult(
                        start=0,
                        added=item_count,
                        removed=0,
                        unchanged=0,
                        difference=item_count,
                        final=item_count,
                    )

            if not isinstance(playlist, RemoteMutablePlaylist):
                self.logger.warning(f"Playlist {playlist.name!r} could not be updated as it is not writeable.")
                return

            playlist.tracks.replace(await api.tracks.get_many(items))

            return playlist.name, await playlist.sync_items(api=api, kind="refresh", dry_run=dry_run)
