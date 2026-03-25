from typing import Annotated, Self, Any

import tabulate
from pydantic import PrivateAttr

from musify.logger import STAT
from musify.models.api import RemoteAPI, HasAPI, HasSavedEndpoints, ReadSavedEndpoints
from musify.models.api.album import AlbumReadSavedEndpoints, HasAlbumEndpoints, AlbumReadCollectionEndpoints
from musify.models.api.artist import HasArtistEndpoints, ArtistReadSavedEndpoints, ArtistReadCollectionEndpoints
from musify.models.api.playlist import HasPlaylistEndpoints, PlaylistReadSavedEndpoints, PlaylistReadWriteEndpoints
from musify.models.api.track import HasTrackEndpoints, TrackReadSavedEndpoints
from musify.models.api.user import HasUserEndpoints
from musify.models.collection import RemoteCollection
from musify.models.collection.album import RemoteAlbumCollection
from musify.models.collection.artist import RemoteArtistCollection
from musify.models.collection.library import Library
from musify.models.collection.library._remote._result import RemoteTracksResult, RemoteArtistsResult, \
    RemoteAlbumsResult, RemotePlaylistsResult
from musify.models.collection.playlist import RemotePlaylist
from musify.models.item.album import RemoteAlbum, HasAlbums
from musify.models.item.artist import RemoteArtist, HasArtists
from musify.models.item.genre import RemoteGenre, HasGenres
from musify.models.item.track import RemoteTrack
from musify.models.metadata import Attribute
from musify.models.result import Result
from musify.models.user import RemoteUser


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
    @property
    def user(self) -> Annotated[UT | None, Attribute()]:
        """The currently authenticated user."""
        if isinstance(self.api, HasUserEndpoints):
            return self.api.users.user

    @property
    def _log_name(self) -> str:
        source = self.source.title()
        if self.user is None:
            return source
        return f"{self.user.name}'s {source}"

    async def __aenter__(self) -> Self:
        await self.api.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.api.__aexit__(exc_type, exc_val, exc_tb)

    async def load(self):
        self.logger.info(f"Loading {self._log_name} library", header=1)

        await self.load_playlists()
        # await self.load_playlist_items()  # TODO: ADD ME BACK

        await self.load_tracks()

        await self.load_saved_albums()
        await self.load_saved_album_tracks()

        # await self.load_saved_artists()  # TODO: ADD ME BACK
        # await self.load_saved_artist_albums()  # TODO: ADD ME BACK

        self.logger.print_line(STAT)

        header = f"{self._log_name.upper()} LIBRARY"
        results: dict[str, Result | None] = self._generate_playlist_results()
        results[tabulate.SEPARATING_LINE] = None
        results["SAVED TRACKS"] = self._generate_track_results()
        results["SAVED ARTISTS"] = self._generate_artist_results()
        results["SAVED ALBUMS"] = self._generate_album_results()
        table = Result.generate_table(results=results, header=header)

        self.logger.print_line(STAT)
        self.logger.stat(table)

    def dump(self) -> dict[str, Any]:
        names_seen = set()
        playlists = []
        for pl in self.playlists.values():
            if pl.name in names_seen:
                continue

            pl_backup = pl.model_dump(exclude={"tracks"})
            pl_backup["tracks"] = [str(track.uri) for track in pl.tracks]
            playlists.append(pl_backup)

        return {
            "tracks": [str(track.uri) for track in self.tracks],
            "playlists": playlists,
            "albums": [str(album.uri) for album in self.albums],
            "artists": [str(artist.uri) for artist in self.artists],
            "genres": [str(genre.uri) for genre in self.genres],
        }

    @staticmethod
    def _should_extend(item: Any) -> bool:
        return isinstance(item, RemoteCollection) and not item.has_all_items

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
        api: HasPlaylistEndpoints[HasSavedEndpoints[PlaylistReadSavedEndpoints]] = self.api

        self.logger.info(f"Loading {self._log_name} playlists", header=2)
        playlists = await api.playlists.saved.get_all()
        if self.playlist_filter is not None:
            playlists: list[VP] = [pl for pl in playlists if self.playlist_filter.check(pl.name)]

        playlists_mapped = {pl.name: pl for pl in sorted(playlists, key=lambda pl: pl.name.casefold())}
        # noinspection PyProtectedMember
        self.playlists._replace(playlists_mapped, extract_keys=False)

        return True

    @HasAPI._validate_api(
        "playlist",
        False,
        (None, HasPlaylistEndpoints, "{type} endpoints"),
        ("playlists", PlaylistReadWriteEndpoints, "reading data for {type} items"),
    )
    async def load_playlist_items(self) -> bool:
        """Load all playlist items for all currently loaded playlists."""
        api: HasPlaylistEndpoints[PlaylistReadWriteEndpoints] = self.api

        playlists = list(filter(self._should_extend, self.playlists.values()))
        if not playlists:
            return False

        self.logger.info(f"Loading tracks for {len(playlists)} playlists in {self._log_name} library", header=2)

        async def _extend_playlist_tracks(pl: VP) -> None:
            items = await api.playlists.get_all(pl, show_bar=False)
            # noinspection PyProtectedMember
            pl.tracks._replace(items)

        await self.logger.get_asynchronous_iterator(
            map(_extend_playlist_tracks, playlists),
            desc=f"Loading {self.source.title()} playlist tracks",
            unit="playlists",
            initial=0,
            total=len(playlists),
        )

        return True

    def log_playlists(self) -> None:
        results = self._generate_playlist_results()
        header = f"{self._log_name.upper()} PLAYLISTS"
        table = RemotePlaylistsResult.generate_table(results=results, header=header)

        self.logger.stat(table)

    def _generate_playlist_results(self) -> dict[str, RemotePlaylistsResult[VP]]:
        return RemotePlaylistsResult.from_playlists(playlists=self.playlists.values())

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
        api: HasTrackEndpoints[HasSavedEndpoints[TrackReadSavedEndpoints]] = self.api

        self.logger.info(f"Loading {self._log_name} saved tracks", header=2)
        tracks = await api.tracks.saved.get_all()
        # noinspection PyProtectedMember
        self.tracks._replace(tracks)

        return True

    def log_tracks(self) -> None:
        result = self._generate_track_results()
        key = f"{self._log_name.upper()} TRACKS"
        table = result.generate_table(results={key: result})

        self.logger.stat(table)

    def _generate_track_results(self) -> RemoteTracksResult[TV]:
        return RemoteTracksResult.from_library(self.tracks, self.playlists.values(), self.albums)

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
        api: HasArtistEndpoints[HasSavedEndpoints[AlbumReadSavedEndpoints]] = self.api

        self.logger.info(f"Loading {self._log_name} saved artists", header=2)
        artists = await api.artists.saved.get_all()

        self.artists.clear()
        self.artists.extend(artists)

        return True

    @HasAPI._validate_api(
        "artist",
        False,
        (None, HasPlaylistEndpoints, "{type} endpoints"),
        ("artists", ArtistReadCollectionEndpoints, "reading data for saved {type}'s albums"),
    )
    async def load_saved_artist_albums(self) -> bool:
        """Load all artists albums for all currently loaded albums."""
        api: HasArtistEndpoints[ArtistReadCollectionEndpoints] = self.api

        artists = list(filter(self._should_extend, self.artists))
        if not artists:
            return False

        self.logger.info(f"Loading albums for {len(artists)} saved artists in {self._log_name} library", header=2)

        async def _extend_artist_albums(artist: RemoteArtistCollection) -> None:
            albums = await api.artists.get_all(artist, show_bar=False)
            artist.albums.clear()
            artist.albums.extend(albums)

        await self.logger.get_asynchronous_iterator(
            map(_extend_artist_albums, artists),
            desc=f"Loading {self.source.title()} artist albums",
            unit="artists",
            initial=0,
            total=len(artists),
        )

        return True

    def log_artists(self) -> None:
        """Log stats on currently loaded artists."""
        result = self._generate_artist_results()
        key = f"{self._log_name.upper()} ARTISTS"
        table = result.generate_table(results={key: result})

        self.logger.stat(table)

    def _generate_artist_results(self) -> RemoteArtistsResult[RT]:
        return RemoteArtistsResult(artists=self.artists)

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
        api: HasAlbumEndpoints[HasSavedEndpoints[ReadSavedEndpoints]] = self.api

        self.logger.info(f"Loading {self._log_name} saved albums", header=2)
        albums = await api.albums.saved.get_all()

        self.albums.clear()
        self.albums.extend(albums)

        return True

    @HasAPI._validate_api(
        "album",
        False,
        (None, HasAlbumEndpoints, "{type} endpoints"),
        ("albums", AlbumReadCollectionEndpoints, "reading data for saved {type}'s tracks"),
    )
    async def load_saved_album_tracks(self) -> bool:
        """Load all album tracks for all currently loaded albums."""
        api: HasAlbumEndpoints[AlbumReadCollectionEndpoints] = self.api

        albums = list(filter(self._should_extend, self.albums))
        if not albums:
            return True

        self.logger.info(f"Loading tracks for {len(albums)} saved albums in {self._log_name} library", header=2)

        async def _extend_album_tracks(album: RemoteAlbumCollection) -> None:
            tracks = await api.albums.get_all(album, show_bar=False)
            # noinspection PyProtectedMember
            album.tracks._replace(tracks)

        await self.logger.get_asynchronous_iterator(
            map(_extend_album_tracks, albums),
            desc=f"Loading {self.source.title()} album tracks",
            unit="albums",
            initial=0,
            total=len(albums),
        )

        return True

    def log_albums(self) -> None:
        """Log stats on currently loaded albums."""
        result = self._generate_album_results()
        key = f"{self._log_name.upper()} ALBUMS"
        table = result.generate_table(results={key: result})

        self.logger.stat(table)

    def _generate_album_results(self) -> RemoteAlbumsResult[AT]:
        return RemoteAlbumsResult(albums=self.albums)
