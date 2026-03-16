import textwrap
from abc import abstractmethod
from collections.abc import Mapping, Collection, Sequence
from typing import ClassVar, Self, Any, Literal

from aiorequestful.response.exception import ResponseError
from pydantic import Field, PrivateAttr, validate_call
from tabulate import tabulate
from termcolor import colored

from musify.exception import MusifyTypeError
from musify.logger import STAT
from musify.models.api import RemoteAPI, HasAPI, HasSavedEndpoints, ReadSavedEndpoints, WriteSavedEndpoints
from musify.models.api.album import HasAlbumEndpoints, AlbumReadCollectionEndpoints, AlbumReadSavedEndpoints, \
    AlbumWriteSavedEndpoints, AlbumReadItemsEndpoints
from musify.models.api.artist import HasArtistEndpoints, ArtistReadCollectionEndpoints, ArtistReadSavedEndpoints, \
    ArtistWriteSavedEndpoints, ArtistReadItemsEndpoints
from musify.models.api.playlist import HasPlaylistEndpoints, PlaylistReadSavedEndpoints, \
    PlaylistReadWriteSavedEndpoints, PlaylistReadWriteEndpoints
from musify.models.api.track import HasTrackEndpoints, TrackReadSavedEndpoints, TrackWriteSavedEndpoints, \
    TrackReadItemsEndpoints
from musify.models.api.user import HasUserEndpoints
from musify.models.collection import SyncResult
from musify.models.collection._sync import SYNC_TYPE, get_sync_items, get_sync_message
from musify.models.collection.album import RemoteAlbumCollection
from musify.models.collection.artist import RemoteArtistCollection
from musify.models.collection.playlist import Playlist, HasPlaylists, HasMutablePlaylists, RemotePlaylist, \
    RemoteMutablePlaylist
from musify.models.item.album import RemoteAlbum, HasAlbums
from musify.models.item.artist import RemoteArtist, HasArtists
from musify.models.item.genre import RemoteGenre, HasGenres
from musify.models.item.track import Track, HasTracks, HasMutableTracks, RemoteTrack
from musify.models.properties.logger import HasLogger
from musify.models.properties.uri import HasURI, URI
from musify.models.user import RemoteUser
from musify.processors_new.filters import ValuesFilter

type RestoreType[T] = Sequence[Mapping[str, Any]] | Mapping[T, Mapping[str, Any]]
type RestoreSavedItemsType[T] = RestoreType[T] | Sequence[str | URI]
type RestorePlaylistsType[T] = RestoreType[T] | Mapping[T, Sequence[Mapping[str, Any]]]


class HasTracksAndPlaylists[TK, TV: Track, KP, VP: Playlist](HasTracks[TK, TV], HasPlaylists[KP, VP]):
    @property
    def tracks_in_playlists(self) -> list[TV]:
        """All unique tracks from all playlists in this library"""
        tracks: list[TV] = []

        for pl in self.playlists.values():
            for track in pl.tracks:
                if track not in tracks and track not in self.tracks:
                    tracks.append(track)

        return tracks

    def dump(self) -> dict[str, Any]:
        """Generate a dump of this library's state. This can be used for backup or debugging purposes."""
        return self.model_dump(mode="json", exclude_none=True)


# noinspection PyAbstractClass
class Library[TK, TV: Track, KP, VP: Playlist](
    HasTracksAndPlaylists[TK, TV, KP, VP], HasLogger
):
    """A library of tracks and playlists and other object types."""
    type: ClassVar[str] = "library"

    source: ClassVar[str] = Field(
        description="The name of the source of this library.",
    )

    playlist_filter: ValuesFilter[str] | None = Field(
        description="The filter to apply when loading playlists. Filters playlist by name.",
        default=None
    )

    @abstractmethod
    async def load(self):
        """Loads all resources in this library and log results. Replaces all loaded resources."""
        raise NotImplementedError

    @abstractmethod
    async def load_tracks(self) -> bool:
        """Loads all tracks available for this library. Replaces all currently loaded tracks."""
        raise NotImplementedError

    @abstractmethod
    def log_tracks(self, skip_log: bool = False) -> tuple[str, ...]:
        """Log stats on currently loaded tracks"""
        raise NotImplementedError

    @abstractmethod
    async def load_playlists(self) -> bool:
        """
        Load all playlists available for this library filtered down using the ``playlist_filter`` if given.
        Replaces all currently loaded playlists.
        """
        raise NotImplementedError

    @abstractmethod
    def log_playlists(self, skip_log: bool = False) -> list[tuple[str, ...]]:
        """Log stats on currently loaded playlists"""
        raise NotImplementedError


# noinspection PyAbstractClass
class MutableLibrary[TK, TV: Track, KP, VP: Playlist](
    HasMutableTracks[TK, TV], HasMutablePlaylists[KP, VP], Library[TK, TV, KP, VP]
):
    """A mutable library of tracks and playlists and other object types."""


class RemoteLibrary[
    TK,
    TV: RemoteTrack,
    KP,
    VP: RemotePlaylist,
    API: RemoteAPI,
    RT: RemoteArtist,
    AT: RemoteAlbum,
    GT: RemoteGenre,
    UT: RemoteUser,
](
    Library[TK, TV, KP, VP], HasAPI[API], HasArtists[RT], HasAlbums[AT], HasGenres[GT],
):
    _log_name_max_width: ClassVar[int] = PrivateAttr(default=40)

    _user: UT = PrivateAttr(
        # description="The currently authenticated user for this library."
        default=None
    )

    @property
    def user(self) -> UT | None:
        """The currently authenticated user."""
        return self._user

    @property
    def tracks_in_albums(self) -> list[Track]:
        """All unique tracks from all albums in this collection"""
        tracks: list[Track] = []
        for album in self.albums:
            if not isinstance(album, HasTracks):
                continue

            for track in album.tracks:
                if track not in tracks:
                    tracks.append(track)

        return tracks

    @property
    def _log_name(self) -> str:
        source = self.source.title()
        if self.user is None:
            return source
        return f"{self.user.name}'s {source}"

    @property
    def _log_column_widths(self) -> tuple[int, ...]:
        total = len(self.tracks) + len(self.tracks_in_playlists) + len(self.tracks_in_albums)
        return (
            len(f"{self._log_name.upper()} PLAYLISTS"),
            len(f"{total} artist tracks"),
            len(f"{total} artist albums"),
            len(f"{total} in saved albums"),
            len(f"{total} total tracks"),
        )

    async def __aenter__(self) -> Self:
        await self.api.__aenter__()
        if isinstance(self.api, HasUserEndpoints):
            self._user = await self.api.users.get_me()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.api.__aexit__(exc_type, exc_val, exc_tb)

    async def load(self):
        self.logger.debug(f"Load {self._log_name} library: START")
        self.logger.info(f"\33[1;95m ->\33[1;97m Loading {self._log_name} library \33[0m")

        await self.load_playlists()
        await self.load_playlist_items()

        await self.load_tracks()

        await self.load_saved_albums()
        await self.load_saved_album_tracks()

        await self.load_saved_artists()
        await self.load_saved_artist_albums()

        self.logger.print_line(STAT)
        self.log_playlists(skip_log=True)
        self.log_tracks()
        self.log_albums()
        self.log_artists()

        self.logger.print_line()
        self.logger.debug(f"Load {self._log_name} library: DONE\n")

    ###########################################################################
    ## Load - playlists
    ###########################################################################
    @HasAPI._validate_api(
        "playlist",
        False,
        (None, HasPlaylistEndpoints, "{type} endpoints"),
        ("playlists", HasSavedEndpoints, "saved {type}s endpoints"),
        ("playlists.saved", PlaylistReadSavedEndpoints, "reading data for saved {type}s"),
    )
    async def load_playlists(self) -> bool:
        self.logger.debug(f"Load {self._log_name} playlists: START")
        api: HasPlaylistEndpoints[HasSavedEndpoints[PlaylistReadSavedEndpoints]] = self.api

        playlists = await api.playlists.saved.get_by_user(self.user)
        if self.playlist_filter is not None:
            playlists: list[VP] = [pl for pl in playlists if self.playlist_filter.check(pl.name)]

        playlists_mapped = {pl.name: pl for pl in sorted(playlists, key=lambda pl: pl.name.casefold())}
        # noinspection PyProtectedMember
        self.playlists._replace(playlists_mapped, extract_keys=False)

        self.logger.debug(f"Load {self._log_name} playlists: DONE")
        return True

    @HasAPI._validate_api(
        "playlist",
        False,
        (None, HasPlaylistEndpoints, "{type} endpoints"),
        ("playlists", PlaylistReadWriteEndpoints, "reading data for {type} items"),
    )
    async def load_playlist_items(self) -> bool:
        """Load all playlist items for all currently loaded playlists."""
        self.logger.debug(f"Load {self._log_name} playlist's tracks: START")
        api: HasPlaylistEndpoints[PlaylistReadWriteEndpoints] = self.api

        async def _load_playlist_tracks(pl: VP) -> None:
            items = await api.playlists.get_all(pl)
            # noinspection PyProtectedMember
            pl.tracks._replace(items)

        await self.logger.get_asynchronous_iterator(
            map(_load_playlist_tracks, self.playlists.values()),
            total=len(self.playlists),
            desc=f"Loading {self.source.title()} playlist tracks",
            unit="playlists",
        )

        self.logger.debug(f"Load {self._log_name} playlist's tracks: DONE")
        return True

    def log_playlists(self, skip_log: bool = False) -> list[tuple[str, ...]]:
        widths = self._log_column_widths

        rows = []
        for name, playlist in self.playlists.items():
            iter_widths = iter(widths)
            next(iter_widths)  # don't need header width for this log

            name = textwrap.shorten(name.rjust(next(iter_widths)), self._log_name_max_width, placeholder="...")
            row = (
                colored(name, "white"),
                colored(f"{len(playlist.tracks)} total tracks".rjust(next(iter_widths)), "green"),
            )
            rows.append(row)

        if not rows:
            return rows

        if not skip_log:
            header = colored(f"{self._log_name.upper()} PLAYLISTS", "cyan", attrs=["bold"])
            log = header + ":\n" + tabulate(
                rows,
                tablefmt="orgtbl",
                colalign=("left", "right"),
            )

            self.logger.stat(log)

        return rows

    ###########################################################################
    ## Load - tracks
    ###########################################################################
    @HasAPI._validate_api(
        "track",
        False,
        (None, HasTrackEndpoints, "{type} endpoints"),
        ("tracks", HasSavedEndpoints, "saved {type}s endpoints"),
        ("tracks.saved", TrackReadSavedEndpoints, "reading data for saved {type}s"),
    )
    async def load_tracks(self) -> bool:
        self.logger.debug(f"Load {self._log_name} saved tracks: START")
        api: HasTrackEndpoints[HasSavedEndpoints[TrackReadSavedEndpoints]] = self.api

        tracks = await api.tracks.saved.get_all()
        # noinspection PyProtectedMember
        self.tracks._replace(tracks)

        self.logger.debug(f"Load {self._log_name} saved tracks: DONE")
        return True

    def log_tracks(self, skip_log: bool = False) -> tuple[str, ...]:
        in_tracks = len(self.tracks)
        in_playlists = len(self.tracks_in_playlists)
        in_albums = len(self.tracks_in_albums)

        total = in_tracks + in_playlists + in_albums
        widths = iter(self._log_column_widths)

        header = textwrap.shorten(f"{self._log_name.upper()} TRACKS", self._log_name_max_width, placeholder="...")
        row = (
            colored(f"{header:<{next(widths)}}", "cyan", attrs=["bold"]),
            colored(f"{in_tracks} saved tracks".rjust(next(widths)), "green"),
            colored(f"{in_playlists} in playlists".rjust(next(widths)), "green"),
            colored(f"{in_albums} in saved albums".rjust(next(widths)), "green"),
            colored(f"{total} total tracks".rjust(next(widths)), "blue", attrs=["bold"]),
        )

        if not skip_log:
            log = tabulate(
                [row],
                tablefmt="orgtbl",
                colalign=("left", "right", "right", "right"),
            )
            self.logger.stat(log)

        return row

    ###########################################################################
    ## Load - artists
    ###########################################################################
    @HasAPI._validate_api(
        "artist",
        False,
        (None, HasArtistEndpoints, "{type} endpoints"),
        ("artists", HasSavedEndpoints, "saved {type}s endpoints"),
        ("artists.saved", ArtistReadSavedEndpoints, "reading data for saved {type}s"),
    )
    async def load_saved_artists(self) -> bool:
        """Load all artists available for this library. Replaces all currently loaded artists."""
        self.logger.debug(f"Load {self._log_name} saved artists: START")
        api: HasArtistEndpoints[HasSavedEndpoints[AlbumReadSavedEndpoints]] = self.api

        artists = await api.artists.saved.get_all()

        self.artists.clear()
        self.artists.extend(artists)

        self.logger.debug(f"Load {self._log_name} saved artists: DONE")
        return True

    @HasAPI._validate_api(
        "artist",
        False,
        (None, HasPlaylistEndpoints, "{type} endpoints"),
        ("artists", ArtistReadCollectionEndpoints, "reading data for saved {type}'s albums"),
    )
    async def load_saved_artist_albums(self) -> bool:
        """Load all artists albums for all currently loaded albums."""
        self.logger.debug(f"Load {self._log_name} saved artist's albums: START")
        api: HasArtistEndpoints[ArtistReadCollectionEndpoints] = self.api

        for artist in self.artists:
            if not isinstance(artist, RemoteArtistCollection):
                continue

            albums = await api.artists.get_all(artist)
            artist.albums.clear()
            artist.albums.extend(albums)

        self.logger.debug(f"Load {self._log_name} saved artist's albums: DONE")
        return True

    def log_artists(self, skip_log: bool = False) -> tuple[str, ...]:
        """Log stats on currently loaded albums."""
        widths = iter(self._log_column_widths)
        albums = [
            album for artist in self.artists if isinstance(artist, RemoteArtistCollection) for album in artist.albums
        ]

        header = textwrap.shorten(f"{self._log_name.upper()} ARTISTS", self._log_name_max_width, placeholder="...")
        row = (
            colored(header.ljust(next(widths)), "cyan", attrs=["bold"]),
            colored(f"{sum(album.track_total or 0 for album in albums)} artist tracks".rjust(next(widths)), "green"),
            colored(f"{len(albums)} artist albums".rjust(next(widths)), "green"),
            colored(f"{len(self.artists)} total artists".rjust(next(widths)), "blue", attrs=["bold"]),
        )

        if not skip_log:
            log = tabulate(
                [row],
                tablefmt="orgtbl",
                colalign=("left", "right", "right", "right"),
            )
            self.logger.stat(log)

        return row

    ###########################################################################
    ## Load - albums
    ###########################################################################
    @HasAPI._validate_api(
        "album",
        False,
        (None, HasAlbumEndpoints, "{type} endpoints"),
        ("albums", HasSavedEndpoints, "saved {type}s endpoints"),
        ("albums.saved", AlbumReadSavedEndpoints, "reading data for saved {type}s"),
    )
    async def load_saved_albums(self) -> bool:
        """Load all albums available for this library. Replaces all currently loaded albums."""
        self.logger.debug(f"Load {self._log_name} saved albums: START")
        api: HasAlbumEndpoints[HasSavedEndpoints[ReadSavedEndpoints]] = self.api

        albums = await api.albums.saved.get_all()

        self.albums.clear()
        self.albums.extend(albums)

        self.logger.debug(f"Load {self._log_name} saved albums: DONE")
        return True

    @HasAPI._validate_api(
        "album",
        False,
        (None, HasAlbumEndpoints, "{type} endpoints"),
        ("albums", AlbumReadCollectionEndpoints, "reading data for saved {type}'s tracks"),
    )
    async def load_saved_album_tracks(self) -> bool:
        """Load all album tracks for all currently loaded albums."""
        self.logger.debug(f"Load {self._log_name} saved album's tracks: START")
        api: HasAlbumEndpoints[AlbumReadCollectionEndpoints] = self.api

        for album in self.albums:
            if not isinstance(album, RemoteAlbumCollection):
                continue

            tracks = await api.albums.get_all(album)
            # noinspection PyProtectedMember
            album.tracks._replace(tracks)

        self.logger.debug(f"Load {self._log_name} saved album's tracks: DONE")
        return True

    def log_albums(self, skip_log: bool = False) -> tuple[str, ...]:
        """Log stats on currently loaded albums."""
        widths = iter(self._log_column_widths)

        header = textwrap.shorten(f"{self._log_name.upper()} ALBUMS", self._log_name_max_width, placeholder="...")
        row = (
            colored(header.ljust(next(widths)), "cyan", attrs=["bold"]),
            colored(f"{len(self.tracks_in_albums)} album tracks".rjust(next(widths)), "green"),
            colored(f"{sum(len(album.artists) for album in self.albums)} album artists".rjust(next(widths)), "green"),
            colored(f"{len(self.albums)} total albums".rjust(next(widths)), "blue", attrs=["bold"]),
        )

        if not skip_log:
            log = tabulate(
                [row],
                tablefmt="orgtbl",
                colalign=("left", "right", "right", "right"),
            )
            self.logger.stat(log)

        return row

    ###########################################################################
    ## Backup/Restore
    ###########################################################################
    def dump(self) -> dict[str, Any]:
        names_seen = set()
        playlists = []
        for pl in self.playlists.values():
            if pl.name in names_seen:
                continue

            pl_backup = dict(
                name=pl.name,
                description=pl.description,
                tracks=[str(track.uri) for track in pl.tracks],
            )
            playlists.append(pl_backup)

        return {
            "tracks": [str(track.uri) for track in self.tracks],
            "playlists": playlists,
            "albums": [str(album.uri) for album in self.albums],
            "artists": [str(artist.uri) for artist in self.artists],
            "genres": [str(genre.uri) for genre in self.genres],
        }


_SYNC_ITEMS_TYPE = Literal["playlists", "tracks", "artists", "albums"]


class RemoteMutableLibrary[
    TK,
    TV: RemoteTrack,
    KP,
    VP: RemoteMutablePlaylist,
    API: RemoteAPI,
    RT: RemoteArtist,
    AT: RemoteAlbum,
    GT: RemoteGenre,
    UT: RemoteUser
](
    MutableLibrary[TK, TV, KP, VP], RemoteLibrary[TK, TV, KP, VP, API, RT, AT, GT, UT]
):
    ###########################################################################
    ## Create/Sync Playlists
    ###########################################################################
    @HasAPI._validate_api(
        "playlist",
        None,
        (None, HasPlaylistEndpoints, "{type} endpoints"),
        ("playlists", HasSavedEndpoints, "saved {type}s endpoints"),
        ("playlists.saved", PlaylistReadWriteSavedEndpoints, "writing data for saved {type}s"),
    )
    async def create_playlist(self, name: str, **kwargs) -> VP | None:
        """Create a new playlist with the given name and return it."""
        self.logger.debug(f"Create a playlist on {self._log_name} library: START")
        api: HasPlaylistEndpoints[HasSavedEndpoints[PlaylistReadWriteSavedEndpoints]] = self.api

        if name in self.playlists:
            self.logger.warning(f"Playlist with name {name!r} already exists in {self._log_name} library.")
            return self.playlists[name]

        playlist = await api.playlists.saved.create(name=name, **kwargs)
        # noinspection PyProtectedMember
        self.playlists._update({playlist.name: playlist}, extract_keys=False)

        self.logger.debug(f"Create a playlist on {self._log_name} library: DONE")
        return playlist

    @HasAPI._validate_api(
        "playlist",
        dict,
        (None, HasPlaylistEndpoints, "{type} endpoints"),
        ("playlists", PlaylistReadWriteEndpoints, "writing data for {type}s"),
        ("playlists", HasSavedEndpoints, "saved {type}s endpoints"),
        ("playlists.saved", PlaylistReadWriteSavedEndpoints, "writing data for saved {type}s"),
    )
    async def sync_playlist_items(self, kind: SYNC_TYPE = "new", dry_run: bool = False) -> dict[str, SyncResult]:
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
        :return: Map of playlist name to the results of the sync as a :py:class:`SyncResult` object.
        """
        self.logger.debug(f"Sync {self._log_name} playlists: START")
        api: HasPlaylistEndpoints[
            PlaylistReadWriteEndpoints | HasSavedEndpoints[PlaylistReadWriteSavedEndpoints]
        ] = self.api

        playlists = tuple(pl for pl in self.playlists.values() if isinstance(pl, RemoteMutablePlaylist))

        message_context = get_sync_message(kind, item_type="items", from_type=f"from each {self.source} playlist")
        message = self.logger.generate_message(
            f"Synchronising {len(playlists)} {self.source} playlists: {message_context}", header=1
        )
        self.logger.info(message)

        async def _sync_playlist(pl: RemoteMutablePlaylist) -> tuple[str, SyncResult]:
            remote = await api.playlists.saved.get_or_create(pl.name)
            remote.tracks[:] = pl.tracks
            return pl.name, await remote.sync_items(api=api, kind=kind, dry_run=dry_run)
        
        bar = self.logger.get_asynchronous_iterator(
            map(_sync_playlist, playlists),
            total=len(self.playlists),
            desc=f"Synchronising {self.source.title()} playlists",
            unit="playlists",
        )
        results = dict(await bar)

        self.logger.print_line()
        self.logger.debug(f"Sync {self._log_name} playlists: DONE")
        return results

    def log_sync_playlist_items(
            self, results: Mapping[str, SyncResult], skip_log: bool = False
    ) -> list[tuple[str, ...]]:
        """Log stats from the results of a ``sync_playlists`` operation"""
        if not results:
            return []

        rows = []
        for name, result in results.items():
            row = (
                colored(textwrap.shorten(name, self._log_name_max_width, placeholder="..."), "white"),
                colored(f"{result.start} initial", "cyan"),
                colored(f"{result.added} added", "green"),
                colored(f"{result.removed} removed", "red"),
                colored(f"{result.unchanged} unchanged", "yellow"),
                colored(f"{result.difference} difference", "blue"),
                colored(f"{result.final} final", "white", attrs=["bold"]),
            )
            rows.append(row)

        if not rows:
            return rows

        if not skip_log:
            header = colored(f"{self._log_name.upper()} SYNC PLAYLIST RESULTS", "cyan", attrs=["bold"])
            log = header + ":\n" + tabulate(
                rows,
                tablefmt="orgtbl",
                colalign=("left", "right", "right", "right", "right", "right", "right"),
            )

            self.logger.stat(log)

        return rows

    ###########################################################################
    ## Sync saved items
    ###########################################################################
    @HasAPI._validate_api(
        "track",
        None,
        (None, HasTrackEndpoints, "{type} endpoints"),
        ("tracks", HasSavedEndpoints, "saved {type}s endpoints"),
        ("tracks.saved", TrackReadSavedEndpoints, "reading data for saved {type}s"),
        ("tracks.saved", TrackWriteSavedEndpoints, "writing data for saved {type}s"),
    )
    async def sync_tracks(self, kind: SYNC_TYPE = "new", dry_run: bool = False) -> SyncResult:
        """
        Synchronise the current saved track's with the remote service.

        Sync options:
            * 'new': Do not clear any saved tracks from the remote service and only add new tracks.
            * 'refresh': Clear all saved tracks from the remote service first, then add all tracks.
            * 'sync': Clear all saved tracks not currently on the remote service, then add all tracks
                from this library not currently in the remote service.

        :param kind: Sync option for the remote service. See description.
        :param dry_run: Run function, but do not modify the remote service at all.
        :return: The results of the sync as a :py:class:`SyncResult` object.
        """
        self.logger.debug(f"Sync {self._log_name} saved tracks: START")
        api: HasTrackEndpoints[HasSavedEndpoints[TrackReadSavedEndpoints | TrackWriteSavedEndpoints]] = self.api

        result = await self._sync_saved_items(
            kind, items_type="tracks", items=self.tracks, api=api.tracks, dry_run=dry_run
        )

        self.logger.debug(f"Sync {self._log_name} saved tracks: DONE")
        return result

    @HasAPI._validate_api(
        "artist",
        None,
        (None, HasArtistEndpoints, "{type} endpoints"),
        ("artists", HasSavedEndpoints, "saved {type}s endpoints"),
        ("artists.saved", ArtistReadSavedEndpoints, "reading data for saved {type}s"),
        ("artists.saved", ArtistWriteSavedEndpoints, "writing data for saved {type}s"),
    )
    async def sync_artists(self, kind: SYNC_TYPE = "new", dry_run: bool = False) -> SyncResult:
        """
        Synchronise the current saved artist's with the remote service.

        Sync options:
            * 'new': Do not clear any saved artists from the remote service and only add new artists.
            * 'refresh': Clear all saved artists from the remote service first, then add all artists.
            * 'sync': Clear all saved artists not currently on the remote service, then add all artists
                from this library not currently in the remote service.

        :param kind: Sync option for the remote service. See description.
        :param dry_run: Run function, but do not modify the remote service at all.
        :return: The results of the sync as a :py:class:`SyncResult` object.
        """
        self.logger.debug(f"Sync {self._log_name} saved artists: START")
        api: HasArtistEndpoints[HasSavedEndpoints[ArtistReadSavedEndpoints | ArtistWriteSavedEndpoints]] = self.api

        result = await self._sync_saved_items(
            kind, items_type="artists", items=self.artists, api=api.artists, dry_run=dry_run
        )

        self.logger.debug(f"Sync {self._log_name} saved artists: DONE")
        return result

    @HasAPI._validate_api(
        "album",
        None,
        (None, HasAlbumEndpoints, "{type} endpoints"),
        ("albums", HasSavedEndpoints, "saved {type}s endpoints"),
        ("albums.saved", AlbumReadSavedEndpoints, "reading data for saved {type}s"),
        ("albums.saved", AlbumWriteSavedEndpoints, "writing data for saved {type}s"),
    )
    async def sync_albums(self, kind: SYNC_TYPE = "new", dry_run: bool = False) -> SyncResult:
        """
        Synchronise the current saved album's with the remote service.

        Sync options:
            * 'new': Do not clear any saved albums from the remote service and only add new albums.
            * 'refresh': Clear all saved albums from the remote service first, then add all albums.
            * 'sync': Clear all saved albums not currently on the remote service, then add all albums
                from this library not currently in the remote service.

        :param kind: Sync option for the remote service. See description.
        :param dry_run: Run function, but do not modify the remote service at all.
        :return: The results of the sync as a :py:class:`SyncResult` object.
        """
        self.logger.debug(f"Sync {self._log_name} saved albums: START")
        api: HasAlbumEndpoints[HasSavedEndpoints[AlbumReadSavedEndpoints | AlbumWriteSavedEndpoints]] = self.api

        result = await self._sync_saved_items(
            kind, items_type="albums", items=self.albums, api=api.albums, dry_run=dry_run
        )

        self.logger.debug(f"Sync {self._log_name} saved albums: DONE")
        return result

    async def _sync_saved_items(
            self,
            kind: SYNC_TYPE,
            items_type: _SYNC_ITEMS_TYPE,
            items: Collection[HasURI],
            api: HasSavedEndpoints[ReadSavedEndpoints | WriteSavedEndpoints],
            dry_run: bool,
    ) -> SyncResult:
        """Run a sync of the given type by calling the given add and remove functions with the appropriate items."""
        message_context = get_sync_message(kind, item_type=items_type, from_type="from the library")
        message = self.logger.generate_message(
            f"Synchronising {len(items)} {self.source} {items_type}: {message_context}", header=1
        )
        self.logger.info(message)

        initial = [item.uri for item in items if item.uri]
        remote = await api.saved.get_all()
        add, remove, unchanged = get_sync_items(kind, initial=initial, remote=remote)

        if dry_run:
            removed = len(remove)
            added = len(add)
        else:
            removed = await api.saved.remove_many(remove)
            added = await api.saved.add_many(add)

        return SyncResult(
            start=len(remote),
            added=added,
            removed=removed,
            unchanged=len(unchanged),
            difference=added - removed,
            final=len(remote) + added - removed
        )

    ###########################################################################
    ## Restore playlists and saved items
    ###########################################################################
    @HasAPI._validate_api(
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
            self, playlists: RestorePlaylistsType[str], dry_run: bool = False,
    ) -> dict[str, SyncResult]:
        """
        Restore saved tracks from a backup to track objects.
        This function updates the remote service and reloads this library's tracks after restoring.

        Playlists may be in the form of either:
            * A sequence of dictionaries where dictionary is ``{<Dump of playlist data>}``
            * A mapping of ``{<URI>: {<Dump of playlist data>}}``
            * A mapping of lists ``{"playlists": [{<Dump of track data>}]}``

        :param playlists: Tracks data. See description for accepted formats.
        :param dry_run: Run function, but do not modify the remote service at all.
        :return: The count of saved tracks on the remote service after the sync.
        """
        self.logger.debug(f"Restore {self._log_name} playlists: START")
        api: (
            HasPlaylistEndpoints[PlaylistReadWriteEndpoints | HasSavedEndpoints[PlaylistReadWriteSavedEndpoints]] |
            HasTrackEndpoints[TrackReadItemsEndpoints]
        ) = self.api

        restored: list[VP] = []
        results: dict[str, SyncResult] = {}

        for pl_dump in self._extract_playlists_from_backup(playlists):
            track_uris = self._extract_uris_from_backup(pl_dump["tracks"], key="tracks")

            try:
                playlist = await api.playlists.get(pl_dump["uri"])
            except ResponseError as exc:
                if not dry_run and exc.response.status == 404:
                    self.logger.warning(
                        f"Playlist with name {pl_dump["name"]!r} does not exist on the remote service. "
                        "Creating a new playlist."
                    )
                    playlist = await api.playlists.saved.create(**pl_dump)
                else:
                    track_count = len(track_uris)
                    results[pl_dump["name"]] = SyncResult(
                        start=0,
                        added=track_count,
                        removed=0,
                        unchanged=0,
                        difference=track_count,
                        final=track_count,
                    )
                    continue

            if not isinstance(playlist, RemoteMutablePlaylist):
                self.logger.warning(f"Playlist {playlist.name!r} could not be updated as it is not writeable.")
                continue

            # noinspection PyProtectedMember
            playlist.tracks._replace(await api.tracks.get_many(track_uris))

            results[playlist.name] = await playlist.sync_items(api=api, kind="refresh", dry_run=dry_run)
            restored.append(playlist)

        # noinspection PyProtectedMember
        self.playlists._replace({pl.name: pl for pl in restored}, extract_keys=False)

        self.logger.debug(f"Restore {self._log_name} saved tracks: DONE")
        return results

    @staticmethod
    def _extract_playlists_from_backup(backup: RestorePlaylistsType[str]) -> tuple[dict[str, Any], ...]:
        if isinstance(backup, Mapping) and "playlists" in backup:
            backup = backup["playlists"]

        match backup:
            case Mapping() as playlists if all(isinstance(pl, Mapping) for pl in playlists.values()):
                return tuple(playlists.values())
            case Collection() as playlists if all(isinstance(pl, Mapping) for pl in playlists):
                return tuple(playlists)
            case _:
                raise MusifyTypeError(f"Unrecognised backup dump format: {type(backup).__name__!r}.")

    @HasAPI._validate_api(
        "track",
        None,
        (None, HasTrackEndpoints, "{type} endpoints"),
        ("tracks", TrackReadItemsEndpoints, "reading data for {type}s"),
        ("tracks", HasSavedEndpoints, "saved {type}s endpoints"),
        ("tracks.saved", TrackReadSavedEndpoints, "reading data for saved {type}s"),
        ("tracks.saved", TrackWriteSavedEndpoints, "writing data for saved {type}s"),
    )
    @validate_call
    async def restore_tracks(self, tracks: RestoreSavedItemsType[str], dry_run: bool = False) -> SyncResult | None:
        """
        Restore saved tracks from a backup to track objects.
        This function updates the remote service and reloads this library's tracks after restoring.

        Tracks may be in the form of either:
            * A sequence of track URIs
            * A sequence of dictionaries where dictionary is ``{<Dump of track data>}``
            * A mapping of ``{<URI>: {<Dump of track data>}}``
            * A mapping of ``{"tracks": {<URI>: {<Dump of track data>}}}``

        :param tracks: Tracks data. See description for accepted formats.
        :param dry_run: Run function, but do not modify the remote service at all.
        :return: The count of saved tracks on the remote service after the sync.
        """
        self.logger.debug(f"Restore {self._log_name} saved tracks: START")
        api: HasTrackEndpoints[
            TrackReadItemsEndpoints | HasSavedEndpoints[TrackReadSavedEndpoints | TrackWriteSavedEndpoints]
        ] = self.api

        uris = self._extract_uris_from_backup(tracks, key="tracks")
        self.tracks[:] = await api.tracks.get_many(uris)
        result = await self.sync_tracks(kind="refresh", dry_run=dry_run)

        self.logger.debug(f"Restore {self._log_name} saved tracks: DONE")
        return result

    @HasAPI._validate_api(
        "artist",
        None,
        (None, HasArtistEndpoints, "{type} endpoints"),
        ("artists", ArtistReadItemsEndpoints, "reading data for {type}s"),
        ("artists", HasSavedEndpoints, "saved {type}s endpoints"),
        ("artists.saved", ArtistReadSavedEndpoints, "reading data for saved {type}s"),
        ("artists.saved", ArtistWriteSavedEndpoints, "writing data for saved {type}s"),
    )
    @validate_call
    async def restore_artists(self, artists: RestoreSavedItemsType[str], dry_run: bool = False) -> SyncResult | None:
        """
        Restore saved artists from a backup dump.
        This function updates the remote service and reloads this library's artists after restoring.

        Artists may be in the form of either:
            * A sequence of Artist URIs
            * A sequence of dictionaries where dictionary is ``{<Dump of artist data>}``
            * A mapping of ``{<URI>: {<Dump of artist data>}}``
            * A mapping of ``{"artists": {<URI>: {<Dump of artist data>}}}``

        :param artists: Artists data. See description for accepted formats.
        :param dry_run: Run function, but do not modify the remote service at all.
        :return: The count of saved artists on the remote service after the sync.
        """
        self.logger.debug(f"Restore {self._log_name} saved artists: START")
        api: HasArtistEndpoints[
            ArtistReadItemsEndpoints | HasSavedEndpoints[ArtistReadSavedEndpoints | ArtistWriteSavedEndpoints]
        ] = self.api

        uris = self._extract_uris_from_backup(artists, key="artists")
        self.artists[:] = await api.artists.get_many(uris)
        result = await self.sync_artists(kind="refresh", dry_run=dry_run)

        self.logger.debug(f"Restore {self._log_name} saved artists: DONE")
        return result

    @HasAPI._validate_api(
        "album",
        None,
        (None, HasAlbumEndpoints, "{type} endpoints"),
        ("albums", AlbumReadItemsEndpoints, "reading data for {type}s"),
        ("albums", HasSavedEndpoints, "saved {type}s endpoints"),
        ("albums.saved", AlbumReadSavedEndpoints, "reading data for saved {type}s"),
        ("albums.saved", AlbumWriteSavedEndpoints, "writing data for saved {type}s"),
    )
    @validate_call
    async def restore_albums(self, albums: RestoreSavedItemsType[str], dry_run: bool = False) -> SyncResult | None:
        """
        Restore saved albums from a backup dump.
        This function updates the remote service and reloads this library's albums after restoring.

        Albums may be in the form of either:
            * A sequence of Album URIs
            * A sequence of dictionaries where dictionary is ``{<Dump of album data>}``
            * A mapping of ``{<URI>: {<Dump of album data>}}``
            * A mapping of ``{"albums": {<URI>: {<Dump of album data>}}}``

        :param albums: Albums data. See description for accepted formats.
        :param dry_run: Run function, but do not modify the remote service at all.
        :return: The count of saved albums on the remote service after the sync.
        """
        self.logger.debug(f"Restore {self._log_name} saved albums: START")
        api: HasAlbumEndpoints[
            AlbumReadItemsEndpoints | HasSavedEndpoints[AlbumReadSavedEndpoints | AlbumWriteSavedEndpoints]
        ] = self.api

        uris = self._extract_uris_from_backup(albums, key="albums")
        self.albums[:] = await api.albums.get_many(uris)
        result = await self.sync_albums(kind="refresh", dry_run=dry_run)

        self.logger.debug(f"Restore {self._log_name} saved albums: DONE")
        return result

    @staticmethod
    def _extract_uris_from_backup(backup: RestoreSavedItemsType[str], key: _SYNC_ITEMS_TYPE) -> tuple[str | URI, ...]:
        if isinstance(backup, Mapping) and key in backup:
            backup = backup[key]

        match backup:
            case Mapping() as items if all(isinstance(item, Mapping) and "uri" in item for item in items.values()):
                return tuple(item["uri"] for item in items.values())
            case Mapping() as items:
                return tuple(items.keys())
            case Collection() as items if all(isinstance(item, Mapping) and "uri" in item for item in items):
                return tuple(item["uri"] for item in items)
            case Collection() as items if not isinstance(items, Mapping) and all(
                    isinstance(item, str | URI) for item in items
            ):
                return tuple(items)
            case _:
                raise MusifyTypeError(f"Unrecognised backup dump format: {type(backup).__name__!r}.")
