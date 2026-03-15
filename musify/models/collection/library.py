import itertools
import textwrap
from abc import abstractmethod
from collections.abc import Iterator, Mapping
from typing import ClassVar, Self, Any

from aiorequestful.types import JSON
from pydantic import Field, PrivateAttr
from tabulate import tabulate
from termcolor import colored

from musify.logger import STAT
from musify.models.api import RemoteAPI, HasAPI, HasSavedEndpoints, ReadSavedEndpoints
from musify.models.api.album import HasAlbumEndpoints, AlbumReadCollectionEndpoints, AlbumReadSavedEndpoints
from musify.models.api.artist import HasArtistEndpoints, ArtistReadCollectionEndpoints, ArtistReadSavedEndpoints
from musify.models.api.playlist import HasPlaylistEndpoints, PlaylistReadSavedEndpoints, \
    PlaylistReadWriteSavedEndpoints, PlaylistReadWriteEndpoints
from musify.models.api.track import HasTrackEndpoints, TrackReadSavedEndpoints
from musify.models.api.user import HasUserEndpoints
from musify.models.collection.album import RemoteAlbumCollection
from musify.models.collection.artist import RemoteArtistCollection
from musify.models.collection.playlist import Playlist, HasPlaylists, HasMutablePlaylists, RemotePlaylist, \
    PLAYLIST_SYNC_TYPE, SyncResultRemotePlaylist, RemoteMutablePlaylist
from musify.models.item.album import RemoteAlbum, HasAlbums
from musify.models.item.artist import RemoteArtist, HasArtists
from musify.models.item.genre import RemoteGenre, HasGenres
from musify.models.item.track import Track, HasTracks, HasMutableTracks, RemoteTrack
from musify.models.properties.logger import HasLogger
from musify.models.user import RemoteUser
from musify.processors_new.filters import ValuesFilter


class HasTracksAndPlaylists[TK, TV: Track, KP, VP: Playlist](HasTracks[TK, TV], HasPlaylists[KP, VP]):
    @property
    def tracks_in_playlists(self) -> list[TV]:
        """All unique tracks from all playlists in this library"""
        def _playlist_tracks_in_tracks(playlist: VP) -> Iterator[TV]:
            return (track for track in playlist.tracks if track not in self.tracks)
        return list(itertools.chain.from_iterable(map(_playlist_tracks_in_tracks, self.playlists.values())))

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

        await self.load_tracks()

        await self.load_playlists()
        await self.load_playlist_items()

        await self.load_saved_albums()
        await self.load_saved_album_tracks()

        await self.load_saved_artists()
        # await self.load_saved_artists_albums()

        self.logger.print_line(STAT)
        self.log_playlists(skip_log=True)
        self.log_tracks()
        self.log_albums()
        self.log_artists()

        self.logger.print_line()
        self.logger.debug(f"Load {self._log_name} library: DONE\n")

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
        ("albums", PlaylistReadWriteEndpoints, "reading data for {type} items"),
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
    ## Create/Sync
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
    async def sync_playlist_items(
            self, kind: PLAYLIST_SYNC_TYPE = "new", dry_run: bool = False,
    ) -> dict[str, SyncResultRemotePlaylist]:
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
        :return: Map of playlist name to the results of the sync as a :py:class:`SyncResultRemotePlaylist` object.
        """
        self.logger.debug(f"Sync {self._log_name} playlists: START")
        api: HasPlaylistEndpoints[
            PlaylistReadWriteEndpoints | HasSavedEndpoints[PlaylistReadWriteSavedEndpoints]
        ] = self.api

        match kind:
            case "new":
                type_message = "adding new items only"
            case "refresh":
                type_message = f"clearing all items from each {self.source} playlist first"
            case "sync":
                type_message = f"clearing extra items from each {self.source} playlist first"

        message = self.logger.generate_message(
            f"Synchronising {len(self.playlists)} {self.source} playlists: {type_message}", header=1
        )
        self.logger.info(message)

        async def _sync_playlist(pl: VP) -> tuple[str, SyncResultRemotePlaylist]:
            remote = await api.playlists.saved.get_or_create(pl.name)
            remote.tracks[:] = pl.tracks
            return pl.name, await remote.sync_items(api=api, kind=kind, dry_run=dry_run)

        bar = self.logger.get_asynchronous_iterator(
            map(_sync_playlist, self.playlists.values()),
            total=len(self.playlists),
            desc=f"Synchronising {self.source.title()} playlists",
            unit="playlists",
        )
        results = dict(await bar)

        self.logger.print_line()
        self.logger.debug(f"Sync {self._log_name} playlists: DONE")
        return results

    def log_sync_playlist_items(
            self, results: Mapping[str, SyncResultRemotePlaylist], skip_log: bool = False
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
