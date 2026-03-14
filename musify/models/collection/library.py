import itertools
import textwrap
from abc import abstractmethod
from collections.abc import Iterator
from typing import ClassVar, Self

from pydantic import Field, PrivateAttr
from tabulate import tabulate
from termcolor import colored

from musify.logger import STAT
from musify.models.api import RemoteAPI, HasSavedEndpoints, ReadSavedEndpoints, ReadCollectionEndpoints
from musify.models.api.album import HasAlbumEndpoints
from musify.models.api.artist import HasArtistEndpoints
from musify.models.api.playlist import HasPlaylistEndpoints, PlaylistReadSavedEndpoints, PlaylistReadWriteEndpoints, \
    PlaylistReadItemEndpoints, PlaylistReadWriteSavedEndpoints
from musify.models.api.track import HasTrackEndpoints
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
from musify.models.remote import RemoteModel
from musify.models.user import RemoteUser
from musify.processors_new.filters import ValuesFilter


class HasTracksAndPlaylists[TK, TV: Track, KP, VP: Playlist](HasTracks[TK, TV], HasPlaylists[KP, VP]):
    @property
    def tracks_in_playlists(self) -> list[TV]:
        """All unique tracks from all playlists in this library"""
        def _playlist_tracks_in_tracks(playlist: VP) -> Iterator[TV]:
            return (track for track in playlist.tracks if track not in self.tracks)
        return list(itertools.chain.from_iterable(map(_playlist_tracks_in_tracks, self.playlists.values())))


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
    RT: RemoteArtist,
    AT: RemoteAlbum,
    GT: RemoteGenre,
    UT: RemoteUser,
](
    Library[TK, TV, KP, VP], RemoteModel, HasArtists[RT], HasAlbums[AT], HasGenres[GT]
):
    _log_name_max_width: ClassVar[int] = PrivateAttr(default=30)

    _user: UT = PrivateAttr(
        # description="The currently authenticated user for this library."
        default=None
    )

    api: RemoteAPI | HasUserEndpoints = Field(
        description="The API client used to interact with the remote service for managing library data."
    )

    @property
    def _log_name(self) -> str:
        source = self.source.title()
        if self.user is None:
            return source
        return f"{self.user.name}'s {source}"

    @property
    def user(self) -> UT | None:
        """The currently authenticated user."""
        return self._user

    async def __aenter__(self) -> Self:
        await self.api.__aenter__()
        if isinstance(self.api, HasUserEndpoints):
            self._user = await self.api.users.get_me()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.api.__aexit__(exc_type, exc_val, exc_tb)

    def _log_unsupported_api(self, kind: str, context: str) -> None:
        print(f"Cannot load {self.source.title()} {kind}. API does not support {context}.")

    async def load(self):
        self.logger.debug(f"Load {self._log_name} library: START")
        self.logger.info(f"\33[1;95m ->\33[1;97m Loading {self._log_name} library \33[0m")

        await self.load_tracks()

        await self.load_playlists()
        await self.load_playlists_tracks()

        await self.load_saved_albums()
        await self.load_saved_albums_tracks()

        await self.load_saved_artists()
        await self.load_saved_artists_albums()

        self.logger.print_line(STAT)
        self.log_playlists()
        self.log_tracks()
        self.log_albums()
        self.log_artists()

        self.logger.print_line()
        self.logger.debug(f"Load {self._log_name} library: DONE\n")

    ###########################################################################
    ## Load - tracks
    ###########################################################################
    async def load_tracks(self) -> bool:
        self.logger.debug(f"Load {self._log_name} saved tracks: START")

        log_kind = "saved tracks"
        if not isinstance(self.api, HasTrackEndpoints):
            self._log_unsupported_api(log_kind, "track endpoints")
            return False
        if not isinstance(self.api.tracks, HasSavedEndpoints):
            self._log_unsupported_api(log_kind, f"{log_kind} endpoints")
            return False
        if not isinstance(self.api.tracks.saved, ReadSavedEndpoints):
            self._log_unsupported_api(log_kind, f"reading data for {log_kind}")
            return False

        tracks = await self.api.tracks.saved.get_all()
        # noinspection PyProtectedMember
        self.tracks._replace(tracks)

        self.logger.debug(f"Load {self._log_name} saved tracks: DONE")
        return True

    def log_tracks(self, skip_log: bool = False) -> tuple[str, ...]:
        in_playlists = len(self.tracks_in_playlists)
        album_tracks = [
            track for album in self.albums if isinstance(album, RemoteAlbumCollection) for track in album.tracks
        ]

        header = textwrap.shorten(f"{self._log_name.upper()} TRACKS", self._log_name_max_width, placeholder="...")
        row = (
            colored(header, "cyan", attrs=["bold"]),
            colored(f"{in_playlists} in playlists", "green"),
            colored(f"{sum(track in album_tracks for track in self.tracks)} in saved albums", "green"),
            colored(f"{len(self.tracks) + in_playlists} total tracks", "blue", attrs=["bold"]),
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
    async def load_playlists(self) -> bool:
        self.logger.debug(f"Load {self._log_name} playlists: START")

        log_kind = "saved playlists"
        if not isinstance(self.api, HasPlaylistEndpoints):
            self._log_unsupported_api(log_kind, "playlist endpoints")
            return False
        if not isinstance(self.api.playlists, HasSavedEndpoints):
            self._log_unsupported_api(log_kind, f"{log_kind} endpoints")
            return False
        if not isinstance(self.api.playlists.saved, PlaylistReadSavedEndpoints):
            self._log_unsupported_api(log_kind, f"reading data for {log_kind}")
            return False

        playlists = await self.api.playlists.saved.get_by_user(self.user)
        if self.playlist_filter is not None:
            playlists: list[VP] = [pl for pl in playlists if self.playlist_filter.check(pl.name)]

        playlists_mapped = {pl.name: pl for pl in sorted(playlists, key=lambda pl: pl.name.casefold())}
        # noinspection PyProtectedMember
        self.playlists._replace(playlists_mapped, extract_keys=False)

        self.logger.debug(f"Load {self._log_name} playlists: DONE")
        return True

    async def load_playlists_tracks(self) -> bool:
        """Load all playlist tracks for all currently loaded playlists."""
        self.logger.debug(f"Load {self._log_name} playlist's tracks: START")

        log_kind = "playlist tracks"
        if not isinstance(self.api, HasPlaylistEndpoints):
            self._log_unsupported_api(log_kind, "playlist endpoints")
            return False
        if not isinstance(self.api.playlists, PlaylistReadWriteEndpoints):
            self._log_unsupported_api(log_kind, f"reading data for {log_kind}")
            return False

        for pl in self.playlists.values():
            items = await self.api.playlists.get_all(pl)
            # noinspection PyProtectedMember
            pl.tracks._replace(items)

        self.logger.debug(f"Load {self._log_name} playlist's tracks: DONE")
        return True

    def log_playlists(self, skip_log: bool = False) -> list[tuple[str, ...]]:
        rows = []
        for name, playlist in self.playlists.items():
            row = (
                colored(textwrap.shorten(name, self._log_name_max_width, placeholder="..."), "white"),
                colored(f"{len(playlist.tracks)} total tracks", "green"),
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
    async def load_saved_albums(self) -> bool:
        """Load all albums available for this library. Replaces all currently loaded albums."""
        self.logger.debug(f"Load {self._log_name} saved albums: START")

        log_kind = "saved albums"
        if not isinstance(self.api, HasAlbumEndpoints):
            self._log_unsupported_api(log_kind, "track endpoints")
            return False
        if not isinstance(self.api.albums, HasSavedEndpoints):
            self._log_unsupported_api(log_kind, f"{log_kind} endpoints")
            return False
        if not isinstance(self.api.albums.saved, ReadSavedEndpoints):
            self._log_unsupported_api(log_kind, f"reading data for {log_kind}")
            return False

        albums = await self.api.albums.saved.get_all()

        self.albums.clear()
        self.albums.extend(albums)

        self.logger.debug(f"Load {self._log_name} saved albums: DONE")
        return True

    async def load_saved_albums_tracks(self) -> bool:
        """Load all album tracks for all currently loaded albums."""
        self.logger.debug(f"Load {self._log_name} saved album's tracks: START")

        log_kind = "saved album's tracks"
        if not isinstance(self.api, HasAlbumEndpoints):
            self._log_unsupported_api(log_kind, "album endpoints")
            return False
        if not isinstance(self.api.albums, ReadCollectionEndpoints):
            self._log_unsupported_api(log_kind, f"reading data for {log_kind}")
            return False

        for album in self.albums:
            if not isinstance(album, RemoteAlbumCollection):
                continue

            tracks = await self.api.albums.get_all(album)
            # noinspection PyProtectedMember
            album.tracks._replace(tracks)

        self.logger.debug(f"Load {self._log_name} saved album's tracks: DONE")
        return True

    def log_albums(self, skip_log: bool = False) -> tuple[str, ...]:
        """Log stats on currently loaded albums."""
        header = textwrap.shorten(f"{self._log_name.upper()} ALBUMS", self._log_name_max_width, placeholder="...")
        row = (
            colored(header, "cyan", attrs=["bold"]),
            colored(f"{sum(album.track_total or 0 for album in self.albums)} album tracks", "green"),
            colored(f"{sum(len(album.artists) for album in self.albums)} album artists", "green"),
            colored(f"{len(self.albums)} total albums", "blue", attrs=["bold"]),
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
    async def load_saved_artists(self) -> bool:
        """Load all artists available for this library. Replaces all currently loaded artists."""
        self.logger.debug(f"Load {self._log_name} saved artists: START")

        log_kind = "saved artists"
        if not isinstance(self.api, HasArtistEndpoints):
            self._log_unsupported_api(log_kind, "artist endpoints")
            return False
        if not isinstance(self.api.artists, HasSavedEndpoints):
            self._log_unsupported_api(log_kind, f"{log_kind} endpoints")
            return False
        if not isinstance(self.api.artists.saved, ReadSavedEndpoints):
            self._log_unsupported_api(log_kind, f"reading data for {log_kind}")
            return False

        artists = await self.api.artists.saved.get_all()

        self.artists.clear()
        self.artists.extend(artists)

        self.logger.debug(f"Load {self._log_name} saved artists: DONE")
        return True

    async def load_saved_artists_albums(self) -> bool:
        """Load all artists albums for all currently loaded albums."""
        self.logger.debug(f"Load {self._log_name} saved artist's albums: START")

        log_kind = "saved artist's albums"
        if not isinstance(self.api, HasArtistEndpoints):
            self._log_unsupported_api(log_kind, "artist endpoints")
            return False
        if not isinstance(self.api.artists, ReadCollectionEndpoints):
            self._log_unsupported_api(log_kind, f"reading data for {log_kind}")
            return False

        for artist in self.artists:
            if not isinstance(artist, RemoteArtistCollection):
                continue

            albums = await self.api.artists.get_all(artist)
            artist.albums.clear()
            artist.albums.extend(albums)

        self.logger.debug(f"Load {self._log_name} saved artist's albums: DONE")
        return True

    def log_artists(self, skip_log: bool = False) -> tuple[str, ...]:
        """Log stats on currently loaded albums."""
        albums = [
            album for artist in self.artists if isinstance(artist, RemoteArtistCollection) for album in artist.albums
        ]

        header = textwrap.shorten(f"{self._log_name.upper()} ARTISTS", self._log_name_max_width, placeholder="...")
        row = (
            colored(header, "cyan", attrs=["bold"]),
            colored(f"{sum(album.track_total or 0 for album in albums)} artist tracks", "green"),
            colored(f"{len(albums)} artist albums", "green"),
            colored(f"{len(self.artists)} total artists", "blue", attrs=["bold"]),
        )

        if not skip_log:
            log = tabulate(
                [row],
                tablefmt="orgtbl",
                colalign=("left", "right", "right", "right"),
            )
            self.logger.stat(log)

        return row


class RemoteMutableLibrary[
    TK,
    TV: RemoteTrack,
    KP,
    VP: RemoteMutablePlaylist,
    RT: RemoteArtist,
    AT: RemoteAlbum,
    GT: RemoteGenre,
    UT: RemoteUser
](
    MutableLibrary[TK, TV, KP, VP], RemoteLibrary[TK, TV, KP, VP, RT, AT, GT, UT]
):
    async def create_playlist(self, name: str, **kwargs) -> RemotePlaylist | None:
        """Create a new playlist with the given name and return it."""
        self.logger.debug(f"Create a playlist on {self._log_name} library: START")

        if name in self.playlists:
            self.logger.warning(f"Playlist with name {name!r} already exists in {self._log_name} library.")
            return self.playlists[name]

        log_kind = "saved playlists"
        if not isinstance(self.api, HasPlaylistEndpoints):
            self._log_unsupported_api(log_kind, "playlist endpoints")
            return None
        if not isinstance(self.api.playlists, PlaylistReadWriteEndpoints):
            self._log_unsupported_api(log_kind, "writing data for playlists")
            return None
        if not isinstance(self.api.playlists, HasSavedEndpoints):
            self._log_unsupported_api(log_kind, f"{log_kind} endpoints")
            return None
        if not isinstance(self.api.playlists.saved, PlaylistReadWriteSavedEndpoints):
            self._log_unsupported_api(log_kind, f"writing data for {log_kind}")
            return None

        playlist = await self.api.playlists.saved.create(name=name, **kwargs)
        # noinspection PyProtectedMember
        self.playlists._update({playlist.name: playlist}, extract_keys=False)

        self.logger.debug(f"Create a playlist on {self._log_name} library: DONE")
        return playlist

    async def sync_playlists(
            self, kind: PLAYLIST_SYNC_TYPE = "new", dry_run: bool = True
    ) -> dict[str, SyncResultRemotePlaylist]:
        """
        Synchronise the playlists in this library with the remote service.

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

        log_kind = "saved playlists"
        if not isinstance(self.api, HasPlaylistEndpoints):
            self._log_unsupported_api(log_kind, "playlist endpoints")
            return {}
        if not isinstance(self.api.playlists, PlaylistReadWriteEndpoints):
            self._log_unsupported_api(log_kind, f"writing data for playlists")
            return {}
        if not isinstance(self.api.playlists, HasSavedEndpoints):
            self._log_unsupported_api(log_kind, f"{log_kind} endpoints")
            return {}
        if not isinstance(self.api.playlists.saved, PlaylistReadWriteSavedEndpoints):
            self._log_unsupported_api(log_kind, f"writing data for {log_kind}")
            return {}

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

        async def _sync_playlist(pl: RemoteMutablePlaylist) -> tuple[str, SyncResultRemotePlaylist]:
            playlist = await self.api.playlists.saved.get_or_create(pl.name)
            playlist.tracks[:] = pl.tracks
            return pl.name, await playlist.sync(items=pl, kind=kind, dry_run=dry_run)

        bar = self.logger.get_asynchronous_iterator(
            map(_sync_playlist, self.playlists.values()),
            desc=f"Synchronising {self.source.title()} playlists",
            unit="playlists"
        )
        results = dict(await bar)

        self.logger.print_line()
        self.logger.debug(f"Sync {self._log_name} playlists: DONE")
        return results
