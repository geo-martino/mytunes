from collections.abc import Sequence
from typing import Annotated, Any, TypedDict

import tabulate

from mytunes.core._collection import RemoteCollection
from mytunes.core._collection.album import RemoteAlbumCollection
from mytunes.core._collection.artist import RemoteArtistCollection
from mytunes.core._collection.library import Library
from mytunes.core._collection.library._remote._result import RemoteTracksResult, RemoteArtistsResult, \
    RemoteAlbumsResult, RemotePlaylistsResult
from mytunes.core._collection.playlist import RemotePlaylist
from mytunes.core.api import RemoteAPI, HasLibraryEndpoints, ItemReadAllEndpoints, \
    CollectionReadEndpoints, HasAPI
from mytunes.core.api.items import HasAlbumEndpoints, HasArtistEndpoints, HasTrackEndpoints
from mytunes.core.api.playlist import HasPlaylistEndpoints, PlaylistReadAllEndpoints, PlaylistReadWriteEndpoints
from mytunes.core.api.user import HasUserEndpoints
from mytunes.core.properties.uri import URI
from mytunes.core.remote import RemoteModel
from mytunes.result import Result
from ...._item.album import RemoteAlbum, HasAlbums
from ...._item.artist import RemoteArtist, HasArtists
from ...._item.genre import RemoteGenre, HasGenres
from ...._item.track import RemoteTrack
from ...._item.user import RemoteUser
from ....api._base import validate_api
from ....._base.attribute import Attribute


class RemotePlaylistDump[UT: URI](TypedDict):
    name: str
    uri: UT
    items: Sequence[str | URI]


class RemoteLibraryDump[UT: URI](TypedDict, total=False):
    playlists: Sequence[RemotePlaylistDump[UT]]
    tracks: Sequence[str | UT]
    artists: Sequence[str | UT]
    albums: Sequence[str | UT]
    genres: Sequence[str | UT]


class RemoteLibrary[
    API: RemoteAPI,
    TT: RemoteTrack,
    PT: RemotePlaylist,
    RT: RemoteArtist,
    AT: RemoteAlbum,
    GT: RemoteGenre,
    UT: RemoteUser,
](
    Library[TT, PT], RemoteModel, HasAPI[API], HasArtists[RT], HasAlbums[AT], HasGenres[GT],
):
    @property
    def user(self) -> Annotated[UT | None, Attribute()]:
        """The currently authenticated user."""
        if isinstance(self.api, HasUserEndpoints):
            return self.api.users.user

    @property
    def _log_name(self) -> str:
        source = self.source
        if self.user is None:
            return source
        return f"{self.user.name}'s {source}"

    async def load(self):
        self._logger.info(f"Loading {self._log_name} library", header=1)

        with self._progress:
            await self.load_playlists()
            await self.load_playlist_items()

            await self.load_tracks()

            await self.load_library_albums()
            await self.load_library_album_tracks()

            await self.load_library_artists()
            await self.load_library_artist_albums()

        header = f"{self._log_name.upper()} LIBRARY"
        results: dict[str, Result | None] = self._generate_playlist_results()
        results[tabulate.SEPARATING_LINE] = None
        results["SAVED TRACKS"] = self._generate_track_results()
        results["SAVED ARTISTS"] = self._generate_artist_results()
        results["SAVED ALBUMS"] = self._generate_album_results()
        table = Result.generate_table(results=results, header=header)

        self._logger.stat(table, new_line_start=True, new_line_end=True)

    def dump(self) -> RemoteLibraryDump[UT]:
        names_seen = set()
        playlists: list[RemotePlaylistDump[UT]] = []
        for pl in self.playlists.unique:
            if pl.name in names_seen:
                continue

            pl_dump = RemotePlaylistDump[UT](
                **pl.model_dump(exclude={"tracks"}),
                items=[str(track.uri) for track in pl.tracks.unique]
            )
            playlists.append(pl_dump)

        return RemoteLibraryDump[UT](
            playlists=playlists,
            tracks=[str(track.uri) for track in self.tracks],
            albums=[str(album.uri) for album in self.albums],
            artists=[str(artist.uri) for artist in self.artists],
            genres=[str(genre.uri) for genre in self.genres],
        )

    @staticmethod
    def _should_extend(item: Any) -> bool:
        return isinstance(item, RemoteCollection) and not item.has_all_items

    ###########################################################################
    ## Load - playlists
    ###########################################################################
    @validate_api(False, HasPlaylistEndpoints, HasLibraryEndpoints, PlaylistReadAllEndpoints)
    async def load_playlists(self) -> bool:
        api: HasPlaylistEndpoints[HasLibraryEndpoints[PlaylistReadAllEndpoints]] = self.api

        self._logger.info(f"Loading {self._log_name} playlists", header=2)

        playlists = await api.playlists.library.get_all()
        if self.playlist_filter is not None:
            playlists: list[PT] = self.playlist_filter.apply(playlists)

        # noinspection PyProtectedMember
        self.playlists._replace(sorted(playlists, key=lambda pl: pl.name.casefold()))

        return True

    @validate_api(False, HasPlaylistEndpoints, PlaylistReadWriteEndpoints)
    async def load_playlist_items(self) -> bool:
        """Load all playlist items for all currently loaded playlists."""
        api: HasPlaylistEndpoints[PlaylistReadWriteEndpoints] = self.api

        playlists = list(filter(self._should_extend, self.playlists.unique))
        if not playlists:
            return False

        self._logger.info(f"Loading tracks for {len(playlists)} playlists in {self._log_name} library", header=2)

        async def _extend_playlist_tracks(pl: PT) -> None:
            async with self.concurrency:
                items = await api.playlists.get_all_items(pl)
            # noinspection PyProtectedMember
            pl.tracks._replace(items)

        task_id = self._progress.add_task(
            description=f"Loading {self.source} playlist tracks", total=len(playlists),
        )
        await self._run_tasks_async(map(_extend_playlist_tracks, playlists), task_id=task_id)

        return True

    def log_playlists(self) -> None:
        results = self._generate_playlist_results()
        header = f"{self._log_name.upper()} PLAYLISTS"
        table = RemotePlaylistsResult.generate_table(results=results, header=header)

        self._logger.stat(table, new_line_start=True, new_line_end=True)

    def _generate_playlist_results(self) -> dict[str, RemotePlaylistsResult[PT]]:
        results = RemotePlaylistsResult.from_playlists(playlists=self.playlists.unique)
        return {result.name: result for result in results}

    ###########################################################################
    ## Load - tracks
    ###########################################################################
    @validate_api(False, HasTrackEndpoints, HasLibraryEndpoints, ItemReadAllEndpoints)
    async def load_tracks(self) -> bool:
        api: HasTrackEndpoints[HasLibraryEndpoints[ItemReadAllEndpoints]] = self.api

        self._logger.info(f"Loading {self._log_name} library tracks", header=2)

        tracks = await api.tracks.library.get_all()
        # noinspection PyProtectedMember
        self.tracks._replace(tracks)

        return True

    def log_tracks(self) -> None:
        result = self._generate_track_results()
        key = f"{self._log_name.upper()} TRACKS"
        table = result.generate_table(results={key: result})

        self._logger.stat(table, new_line_start=True, new_line_end=True)

    def _generate_track_results(self) -> RemoteTracksResult[TT]:
        return RemoteTracksResult.from_library(self.tracks, self.playlists.unique, self.albums)

    ###########################################################################
    ## Load - artists
    ###########################################################################
    @validate_api(False, HasArtistEndpoints, HasLibraryEndpoints, ItemReadAllEndpoints)
    async def load_library_artists(self) -> bool:
        """Load all artists available for this library. Replaces all currently loaded artists."""
        api: HasArtistEndpoints[HasLibraryEndpoints[ItemReadAllEndpoints]] = self.api

        self._logger.info(f"Loading {self._log_name} library artists", header=2)

        artists = await api.artists.library.get_all()
        self.artists.clear()
        self.artists.extend(artists)

        return True

    @validate_api(False, HasArtistEndpoints, CollectionReadEndpoints)
    async def load_library_artist_albums(self) -> bool:
        """Load all artists albums for all currently loaded albums."""
        api: HasArtistEndpoints[CollectionReadEndpoints] = self.api

        artists = list(filter(self._should_extend, self.artists))
        if not artists:
            return False

        self._logger.info(f"Loading albums for {len(artists)} library artists in {self._log_name} library", header=2)

        async def _extend_artist_albums(artist: RemoteArtistCollection) -> None:
            async with self.concurrency:
                albums = await api.artists.get_all_items(artist)

            artist.albums.clear()
            artist.albums.extend(albums)

        task_id = self._progress.add_task(
            description=f"Loading {self.source} artist albums", total=len(artists),
        )
        await self._run_tasks_async(map(_extend_artist_albums, artists), task_id=task_id)

        return True

    def log_artists(self) -> None:
        """Log stats on currently loaded artists."""
        result = self._generate_artist_results()
        key = f"{self._log_name.upper()} ARTISTS"
        table = result.generate_table(results={key: result})

        self._logger.stat(table, new_line_start=True, new_line_end=True)

    def _generate_artist_results(self) -> RemoteArtistsResult[RT]:
        return RemoteArtistsResult(artists=self.artists)

    ###########################################################################
    ## Load - albums
    ###########################################################################
    @validate_api(False, HasAlbumEndpoints, HasLibraryEndpoints, ItemReadAllEndpoints)
    async def load_library_albums(self) -> bool:
        """Load all albums available for this library. Replaces all currently loaded albums."""
        api: HasAlbumEndpoints[HasLibraryEndpoints[ItemReadAllEndpoints]] = self.api

        self._logger.info(f"Loading {self._log_name} library albums", header=2)

        albums = await api.albums.library.get_all()
        self.albums.clear()
        self.albums.extend(albums)

        return True

    @validate_api(False, HasAlbumEndpoints, CollectionReadEndpoints)
    async def load_library_album_tracks(self) -> bool:
        """Load all album tracks for all currently loaded albums."""
        api: HasAlbumEndpoints[CollectionReadEndpoints] = self.api

        albums = list(filter(self._should_extend, self.albums))
        if not albums:
            return True

        self._logger.info(f"Loading tracks for {len(albums)} library albums in {self._log_name} library", header=2)

        async def _extend_album_tracks(album: RemoteAlbumCollection) -> None:
            async with self.concurrency:
                tracks = await api.albums.get_all_items(album)
            # noinspection PyProtectedMember
            album.tracks._replace(tracks)

        task_id = self._progress.add_task(
            description=f"Loading {self.source} album tracks", total=len(albums),
        )
        await self._run_tasks_async(map(_extend_album_tracks, albums), task_id=task_id)

        return True

    def log_albums(self) -> None:
        """Log stats on currently loaded albums."""
        result = self._generate_album_results()
        key = f"{self._log_name.upper()} ALBUMS"
        table = result.generate_table(results={key: result})

        self._logger.stat(table, new_line_start=True, new_line_end=True)

    def _generate_album_results(self) -> RemoteAlbumsResult[AT]:
        return RemoteAlbumsResult(albums=self.albums)
