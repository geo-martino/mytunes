import functools
import re
import textwrap
from abc import abstractmethod
from collections.abc import Mapping, Collection, Sequence
from typing import ClassVar, Self, Any, Literal, Annotated

from aiorequestful.response.exception import ResponseError
from pydantic import Field, PrivateAttr, validate_call, BeforeValidator
from tabulate import tabulate
from termcolor import colored

from musify.exception import MusifyTypeError
from musify.logger import STAT
from musify.models import ResourceModel
from musify.models._metaclass import makecls
from musify.models._metadata import Attribute
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
from musify.models.collection import SyncResult, RemoteCollection
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
    ResourceModel, HasTracksAndPlaylists[TK, TV, KP, VP], HasLogger, metaclass=makecls()
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
    def user(self) -> Annotated[UT | None, Attribute()]:
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

    async def __aenter__(self) -> Self:
        await self.api.__aenter__()
        if isinstance(self.api, HasUserEndpoints):
            self._user = await self.api.users.get_me()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.api.__aexit__(exc_type, exc_val, exc_tb)

    async def load(self):
        self.logger.info(f"Loading {self._log_name} library", header=1)

        await self.load_playlists()
        await self.load_playlist_items()

        await self.load_tracks()

        await self.load_saved_albums()
        await self.load_saved_album_tracks()

        await self.load_saved_artists()
        await self.load_saved_artist_albums()

        self.logger.print_line(STAT)

        rows = self.log_playlists(skip_log=True)
        rows.append(self.log_tracks(skip_log=True))
        rows.append(self.log_albums(skip_log=True))
        rows.append(self.log_artists(skip_log=True))
        self.logger.stat(self._generate_table(rows))

        self.logger.print_line()

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
        playlists = await api.playlists.saved.get_by_user(self.user)
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

    def log_playlists(self, skip_log: bool = False) -> list[tuple[str, ...]]:
        rows = []
        for name, playlist in self.playlists.items():
            name = textwrap.shorten(name, self._log_name_max_width, placeholder="...")
            row = (
                colored(name, "white"),
                colored(f"{len(playlist.tracks)} total tracks", "green"),
            )
            rows.append(row)

        if rows and not skip_log:
            header = colored(f"{self._log_name.upper()} PLAYLISTS", "cyan", attrs=["bold"])
            log = header + ":\n" + self._generate_table(rows)
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
        api: HasTrackEndpoints[HasSavedEndpoints[TrackReadSavedEndpoints]] = self.api

        self.logger.info(f"Loading {self._log_name} saved tracks", header=2)
        tracks = await api.tracks.saved.get_all()
        # noinspection PyProtectedMember
        self.tracks._replace(tracks)

        return True

    def log_tracks(self, skip_log: bool = False) -> tuple[str, ...]:
        in_tracks = len(self.tracks)
        in_playlists = len(self.tracks_in_playlists)
        in_albums = len(self.tracks_in_albums)
        total = in_tracks + in_playlists + in_albums

        header = textwrap.shorten(f"{self._log_name.upper()} TRACKS", self._log_name_max_width, placeholder="...")
        row = (
            colored(header, "cyan", attrs=["bold"]),
            colored(f"{in_tracks} saved tracks", "green"),
            colored(f"{in_playlists} in playlists", "green"),
            colored(f"{in_albums} in saved albums", "green"),
            colored(f"{total} total tracks", "blue", attrs=["bold"]),
        )

        if not skip_log:
            self.logger.stat(self._generate_table([row]))
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
            self.logger.stat(self._generate_table([row]))
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

    def log_albums(self, skip_log: bool = False) -> tuple[str, ...]:
        """Log stats on currently loaded albums."""
        header = textwrap.shorten(f"{self._log_name.upper()} ALBUMS", self._log_name_max_width, placeholder="...")
        row = (
            colored(header, "cyan", attrs=["bold"]),
            colored(f"{len(self.tracks_in_albums)} album tracks", "green"),
            colored(f"{sum(len(album.artists) for album in self.albums)} album artists", "green"),
            colored(f"{len(self.albums)} total albums", "blue", attrs=["bold"]),
        )

        if not skip_log:
            self.logger.stat(self._generate_table([row]))
        return row


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
    async def sync(self, kind: SYNC_TYPE = "new", dry_run: bool = False) -> dict[str, SyncResult]:
        """
        Synchronise all items in this library with the remote service.

        Sync options:
            * 'new': Do not clear any items from the remote service and only add new items.
            * 'refresh': Clear all items from the remote service first, then add all items.
            * 'sync': Clear all items not currently on the remote service, then add all items
                from this library not currently in the remote service.

        :param kind: Sync option for the remote service. See description.
        :param dry_run: Run function, but do not modify the remote service at all.
        :return: Map of item type to the results of the sync as a :py:class:`SyncResult` object.
        """
        self.logger.info(f"Synchronising {self._log_name} library", header=1)

        results = await self.sync_playlist_items(kind=kind, dry_run=dry_run)
        results["TRACKS"] = await self.sync_tracks(kind=kind, dry_run=dry_run)
        results["ARTISTS"] = await self.sync_artists(kind=kind, dry_run=dry_run)
        results["ALBUMS"] = await self.sync_albums(kind=kind, dry_run=dry_run)

        self.log_sync_results(results, skip_log=False)
        return results

    def log_sync_results(
            self, results: Mapping[str, SyncResult], skip_log: bool = False
    ) -> list[tuple[str, ...]]:
        """Log stats from the results of a sync operation"""
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

        if rows and not skip_log:
            header = colored(f"{self._log_name.upper()} SYNC RESULTS", "cyan", attrs=["bold"])
            log = header + ":\n" + self._generate_table(rows)
            self.logger.stat(log)

        return rows

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
        api: HasPlaylistEndpoints[HasSavedEndpoints[PlaylistReadWriteSavedEndpoints]] = self.api

        if name in self.playlists:
            self.logger.warning(f"Playlist with name {name!r} already exists in {self._log_name} library.")
            return self.playlists[name]

        self.logger.info(f"Creating playlist {name!r} on {self._log_name} library", header=2)
        playlist = await api.playlists.saved.create(name=name, **kwargs)
        # noinspection PyProtectedMember
        self.playlists._update({playlist.name: playlist}, extract_keys=False)

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
        api: HasPlaylistEndpoints[
            PlaylistReadWriteEndpoints | HasSavedEndpoints[PlaylistReadWriteSavedEndpoints]
        ] = self.api

        playlists = list(filter(lambda pl: isinstance(pl, RemoteMutablePlaylist), self.playlists.values()))

        message_context = get_sync_message(kind, item_type="items", from_type=f"from each {self.source} playlist")
        message = f"Synchronising {len(playlists)} playlists on {self._log_name} library: {message_context}"
        self.logger.info(message, header=1)

        async def _sync_playlist(pl: RemoteMutablePlaylist) -> tuple[str, SyncResult]:
            remote = await api.playlists.saved.get_or_create(pl.name)
            remote.tracks[:] = pl.tracks
            return pl.name, await remote.sync_items(api=api, kind=kind, dry_run=dry_run, show_bar=False)
        
        bar = self.logger.get_asynchronous_iterator(
            map(_sync_playlist, playlists),
            desc=f"Synchronising {self.source.title()} playlists",
            unit="playlists",
            initial=0,
            total=len(playlists),
        )
        return dict(await bar)

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
        api: HasTrackEndpoints[HasSavedEndpoints[TrackReadSavedEndpoints | TrackWriteSavedEndpoints]] = self.api
        return await self._sync_saved_items(
            kind, items_type="tracks", items=self.tracks, api=api.tracks, dry_run=dry_run
        )

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
        api: HasArtistEndpoints[HasSavedEndpoints[ArtistReadSavedEndpoints | ArtistWriteSavedEndpoints]] = self.api
        return await self._sync_saved_items(
            kind, items_type="artists", items=self.artists, api=api.artists, dry_run=dry_run
        )

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
        api: HasAlbumEndpoints[HasSavedEndpoints[AlbumReadSavedEndpoints | AlbumWriteSavedEndpoints]] = self.api
        return await self._sync_saved_items(
            kind, items_type="albums", items=self.albums, api=api.albums, dry_run=dry_run
        )

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
        message = f"Synchronising {len(items)} {items_type} on {self._log_name} library: {message_context}"
        self.logger.info(message, header=1)

        initial = [item.uri for item in items if item.uri]
        remote = await api.saved.get_all()
        add, remove, unchanged = get_sync_items(kind, initial=initial, remote=remote)

        removed = await api.saved.remove_many(remove) if not dry_run else len(remove)
        added = await api.saved.add_many(add) if not dry_run else len(add)

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

    def restore(
            self, backup: RestoreLibraryType[_SYNC_ITEMS_TYPE], dry_run: bool = False
    ) -> dict[str, SyncResult] | SyncResult | None:
        """
        Restore library from a backup.

        :param backup: Backup data to restore.
        :param dry_run: Run function, but do not modify the remote service at all.
        :return: The results of the restore as a mapping of item type to either a :py:class:`SyncResult` object
            or a mapping of playlist name to :py:class:`SyncResult
        """
        results: dict[str, SyncResult] = {}

        if "playlists" in backup:
            results |= self.restore_playlists(backup, dry_run=dry_run)
        if "tracks" in backup:
            results |= self.restore_tracks(backup, dry_run=dry_run)
        if "artists" in backup:
            results |= self.restore_artists(backup, dry_run=dry_run)
        if "albums" in backup:
            results |= self.restore_albums(backup, dry_run=dry_run)

        self.log_sync_results(results, skip_log=False)
        return results

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
            self,
            playlists: Annotated[
                tuple[tuple[str | URI, dict[str, Any], tuple[str | URI, ...]], ...],
                BeforeValidator(_extract_playlists_from_backup)
            ],
            dry_run: bool = False,
    ) -> dict[str, SyncResult]:
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
        api: (
            HasPlaylistEndpoints[PlaylistReadWriteEndpoints | HasSavedEndpoints[PlaylistReadWriteSavedEndpoints]] |
            HasTrackEndpoints[TrackReadItemsEndpoints]
        ) = self.api

        self.logger.info(f"Restoring {len(playlists)} playlists on {self._log_name} library", header=2)

        restored: list[VP] = []
        results: dict[str, SyncResult] = {}

        for pl_uri, pl_dump, track_uris in playlists:
            try:
                playlist = await api.playlists.get(pl_uri)
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

        return results

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
    async def restore_tracks(
            self,
            uris: Annotated[
                Sequence[str | URI],
                BeforeValidator(functools.partial(_extract_uris_from_backup, key="tracks"))
            ],
            dry_run: bool = False
    ) -> SyncResult | None:
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
    async def restore_artists(
            self,
            uris: Annotated[
                Sequence[str | URI],
                BeforeValidator(functools.partial(_extract_uris_from_backup, key="artists"))
            ],
            dry_run: bool = False
    ) -> SyncResult | None:
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
    async def restore_albums(
            self,
            uris: Annotated[
                Sequence[str | URI],
                BeforeValidator(functools.partial(_extract_uris_from_backup, key="albums"))
            ],
            dry_run: bool = False
    ) -> SyncResult | None:
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
