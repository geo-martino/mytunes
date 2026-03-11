import itertools
import textwrap
from abc import abstractmethod
from collections.abc import Iterator
from typing import ClassVar, Self

from pydantic import Field, PrivateAttr, field_validator
from tabulate import tabulate
from termcolor import colored

from musify.logger import STAT
from musify.models.remote import RemoteModel
from musify.models.collection.album import RemoteAlbumCollection
from musify.models.collection.artist import RemoteArtistCollection

from musify.models.collection.playlist import Playlist, HasPlaylists, HasMutablePlaylists, RemotePlaylist
from musify.models.item.album import RemoteAlbum, HasAlbums
from musify.models.item.artist import RemoteArtist, HasArtists
from musify.models.item.genre import RemoteGenre, HasGenres
from musify.models.item.track import Track, HasTracks, HasMutableTracks, RemoteTrack
from musify.models.properties.logger import HasLogger
from musify.models.user import RemoteUser
from musify.processors_new.filters import ValuesFilter
from musify.models.api import RemoteAPI, HasSavedEndpoints
from musify.models.api.album import HasAlbumEndpoints, AlbumReadSavedEndpoints
from musify.models.api.artist import HasArtistEndpoints, ArtistReadSavedEndpoints
from musify.models.api.exception import APIError
from musify.models.api.playlist import HasPlaylistEndpoints, PlaylistReadSavedEndpoints, PlaylistReadWriteEndpoints
from musify.models.api.track import HasTrackEndpoints, TrackReadSavedEndpoints
from musify.models.api.user import HasUserEndpoints


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
    async def load_tracks(self) -> None:
        """Loads all tracks available for this library. Replaces all currently loaded tracks."""
        raise NotImplementedError

    @abstractmethod
    def log_tracks(self, skip_log: bool = False) -> tuple[str, ...]:
        """Log stats on currently loaded tracks"""
        raise NotImplementedError

    @abstractmethod
    async def load_playlists(self) -> None:
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
    TK, TV: RemoteTrack, KP, VP: RemotePlaylist, RT: RemoteArtist, AT: RemoteAlbum, GT: RemoteGenre, UT: RemoteUser
](
    Library[TK, TV, KP, VP], RemoteModel, HasArtists[RT], HasAlbums[AT], HasGenres[GT]
):
    _log_name_max_width: ClassVar[int] = PrivateAttr(default=30)

    _user: UT = PrivateAttr(default=None)

    api: RemoteAPI | HasUserEndpoints = Field(
        description="The API client used to interact with the remote service for managing library data."
    )

    @field_validator("api", mode="after", check_fields=True)
    @classmethod
    def _has_necessary_endpoints(cls, api: RemoteAPI) -> RemoteAPI | HasUserEndpoints:
        if not isinstance(api, HasUserEndpoints):
            raise APIError(
                "The provided API client does not support user endpoints, which are required to access the "
                "library's user information."
            )
        return api

    @property
    def _log_name(self) -> str:
        return f"{self.user.name}'S {self.source}"

    @property
    def user(self) -> UT:
        """The currently authenticated user."""
        return self._user

    async def __aenter__(self) -> Self:
        await self.api.__aenter__()
        self._user = await self.api.users.get_me()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.api.__aexit__(exc_type, exc_val, exc_tb)

    async def load(self):
        library_name = f"{self.user.name}'s {self.api.source}"
        self.logger.debug(f"Load {library_name} library: START")
        self.logger.info(f"\33[1;95m ->\33[1;97m Loading {library_name} library \33[0m")

        await self.load_playlists()
        await self.load_tracks()
        await self.load_saved_albums()
        await self.load_saved_artists()

        self.logger.print_line(STAT)
        self.log_playlists()
        self.log_tracks()
        self.log_albums()
        self.log_artists()

        self.logger.print_line()
        self.logger.debug(f"Load {library_name} library: DONE\n")

    ###########################################################################
    ## Load - tracks
    ###########################################################################
    async def load_tracks(self) -> None:
        self.logger.debug(f"Load {self._log_name} saved tracks: START")
        if not isinstance(self.api, HasTrackEndpoints):
            return
        if not isinstance(self.api.tracks, HasSavedEndpoints):
            return
        if not isinstance(self.api.tracks.saved, TrackReadSavedEndpoints):
            return

        tracks = await self.api.tracks.saved.get_all()

        self.tracks._items.clear()
        self.tracks._items_mapped.clear()
        self.tracks._items.extend(tracks)
        self.tracks._items_mapped.update(tracks)

        self.logger.debug(f"Load {self._log_name} saved tracks: DONE")

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
    async def load_playlists(self) -> None:
        self.logger.debug(f"Load {self._log_name} playlists: START")
        if not isinstance(self.api, HasPlaylistEndpoints):
            return
        if not isinstance(self.api.playlists, HasSavedEndpoints):
            return
        if not isinstance(self.api.playlists.saved, PlaylistReadSavedEndpoints):
            return
        if not isinstance(self.api.playlists, PlaylistReadWriteEndpoints):
            return

        playlists = await self.api.playlists.saved.get_by_user(self.user)
        playlists_filtered: list[VP] = []
        for pl in playlists:
            if self.playlist_filter is not None and not self.playlist_filter.check(pl.name):
                continue

            items = await self.api.playlists.get_all(pl)
            pl.tracks._items.extend(items)
            pl.tracks._items_mapped.update(items)

            playlists_filtered.append(pl)

        playlists_mapped = {pl.name: pl for pl in sorted(playlists_filtered, key=lambda pl: pl.name.casefold())}

        self.playlists._items.clear()
        self.playlists._items.update(playlists_mapped)

        self.logger.debug(f"Load {self._log_name} playlists: DONE")

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
    async def load_saved_albums(self) -> None:
        """Load all albums available for this library. Replaces all currently loaded albums."""
        self.logger.debug(f"Load {self._log_name} saved albums: START")
        if not isinstance(self.api, HasAlbumEndpoints):
            return
        if not isinstance(self.api.albums, HasSavedEndpoints):
            return
        if not isinstance(self.api.albums.saved, AlbumReadSavedEndpoints):
            return

        albums = await self.api.albums.saved.get_all()

        self.albums.clear()
        self.albums.extend(albums)

        self.logger.debug(f"Load {self._log_name} saved albums: DONE")

    async def enrich_saved_albums(self, *_, **__) -> None:
        """
        Call API to enrich elements of user's saved album objects improving metadata coverage.
        This is an optionally implementable method. Defaults to doing nothing.
        """
        self.logger.debug("Enrich albums not implemented for this library, skipping...")

    def log_albums(self, skip_log: bool = False) -> tuple[str, ...]:
        """Log stats on currently loaded albums."""
        header = textwrap.shorten(f"{self._log_name.upper()} ALBUMS", self._log_name_max_width, placeholder="...")
        row = (
            colored(header, "cyan", attrs=["bold"]),
            colored(f"{sum(album.track_total for album in self.albums)} album tracks", "green"),
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
    async def load_saved_artists(self) -> None:
        """Load all artists available for this library. Replaces all currently loaded artists."""
        self.logger.debug(f"Load {self._log_name} saved artists: START")
        if not isinstance(self.api, HasArtistEndpoints):
            return
        if not isinstance(self.api.artists, HasSavedEndpoints):
            return
        if not isinstance(self.api.artists.saved, ArtistReadSavedEndpoints):
            return

        artists = await self.api.artists.saved.get_all()

        self.artists.clear()
        self.artists.extend(artists)

        self.logger.debug(f"Load {self._log_name} saved artists: DONE")

    async def enrich_saved_artists(self, *_, **__) -> None:
        """
        Call API to enrich elements of user's saved artist objects improving metadata coverage.
        This is an optionally implementable method. Defaults to doing nothing.
        """
        self.logger.debug("Enrich artists not implemented for this library, skipping...")

    def log_artists(self, skip_log: bool = False) -> tuple[str, ...]:
        """Log stats on currently loaded albums."""
        albums = [
            album for artist in self.artists if isinstance(artist, RemoteArtistCollection) for album in artist.albums
        ]

        header = textwrap.shorten(f"{self._log_name.upper()} ARTISTS", self._log_name_max_width, placeholder="...")
        row = (
            colored(header, "cyan", attrs=["bold"]),
            colored(f"{sum(album.track_total for album in albums)} artist tracks", "green"),
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
    TK, TV: RemoteTrack, KP, VP: RemotePlaylist, RT: RemoteArtist, AT: RemoteAlbum, GT: RemoteGenre, UT: RemoteUser
](
    MutableLibrary[TK, TV, KP, VP], RemoteLibrary[TK, TV, KP, VP, RT, AT, GT, UT]
):
    pass
