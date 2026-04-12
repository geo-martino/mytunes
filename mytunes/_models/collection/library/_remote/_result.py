from collections.abc import Iterable, Sequence
from typing import Annotated, Any, Self

from pydantic import Field, computed_field

from mytunes._models.collection.album import AlbumCollection, RemoteAlbumCollection
from mytunes._models.collection.artist import RemoteArtistCollection
from mytunes._models.collection.playlist import Playlist, RemotePlaylist, RemoteMutablePlaylist
from mytunes._models.item.album import RemoteAlbum
from mytunes._models.item.artist import RemoteArtist
from mytunes._models.item.track import RemoteTrack, HasTracks
from mytunes._models.result import CountResult, TotalCountResult, LenLogFormatter, MapLogFormatter, LogFormatter
from mytunes._types import TO_TUPLE

_log_formatters = [
    LenLogFormatter(
        width=6, alignment="right", colour="yellow", colour_attributes=["bold"], condition=lambda x: x == 0
    ),
    LenLogFormatter(
        width=6, alignment="right", colour="green", colour_attributes=["bold"], condition=lambda x: x > 0
    ),
]


class RemotePlaylistsResult[T: RemoteTrack](CountResult):
    owner: Annotated[
        str,
        LogFormatter(colour="magenta", max_width=20, include_name_in_log=False)
    ] = Field(
        description="The owner of the playlist."
    )
    writeable: Annotated[
        bool,
        MapLogFormatter(
            value="WRITEABLE",
            colour="green",
            colour_attributes=["bold"],
            condition=lambda x: x,
            include_name_in_log=False,
        ),
        MapLogFormatter(
            value="READ ONLY",
            colour="blue",
            colour_attributes=["bold"],
            condition=lambda x: not x,
            include_name_in_log=False,
        ),
    ] = Field(
        description="Whether the playlists in this result are writeable (i.e. can be modified by the user).",
    )
    tracks: Annotated[Sequence[T], TO_TUPLE, *_log_formatters] = Field(
        description="The tracks in this result.",
    )

    @classmethod
    def from_playlist(cls, playlist: RemotePlaylist[Any, T, Any, Any]) -> Self:
        """Create a result from the given playlist."""
        return cls(
            tracks=playlist.tracks,
            owner=playlist.owner.name,
            writeable=isinstance(playlist, RemoteMutablePlaylist)
        )

    @classmethod
    def from_playlists(cls, playlists: Iterable[RemotePlaylist[Any, T, Any, Any]]) -> dict[str, Self]:
        """Create a result from the given playlists."""
        return {pl.name: cls.from_playlist(pl) for pl in playlists}


class RemoteTracksResult[T: RemoteTrack](TotalCountResult):
    """The result of loading tracks from a remote library."""
    in_library: Annotated[Sequence[T], TO_TUPLE, *_log_formatters] = Field(
        description="The tracks which are in the library but not in playlists or library albums.",
        default_factory=tuple
    )
    in_playlists: Annotated[Sequence[T], TO_TUPLE, *_log_formatters] = Field(
        description="The tracks which are in playlists in the library but not library tracks.",
        default_factory=tuple
    )
    in_albums: Annotated[Sequence[T], TO_TUPLE, *_log_formatters] = Field(
        description="The tracks which are in the library's library albums but not library tracks.",
        default_factory=tuple
    )

    @classmethod
    def from_library(
            cls,
            tracks: Iterable[T],
            playlists: Iterable[Playlist[Any, T]],
            albums: Iterable[AlbumCollection[Any, T, Any, Any]]
    ) -> Self:
        """Create a result from the given library items."""
        return cls(
            in_library=tracks,
            in_playlists=cls._get_tracks_in_collections(playlists, tracks),
            in_albums=cls._get_tracks_in_collections(albums, tracks),
        )

    @classmethod
    def _get_tracks_in_collections(cls, collections: Iterable[HasTracks[Any, T]], others: Iterable[T]) -> tuple[T, ...]:
        """All unique tracks from all given collections"""
        in_collections: list[T] = []

        for coll in collections:
            for track in coll.tracks:
                if track not in in_collections and track not in others:
                    in_collections.append(track)

        return tuple(in_collections)


class RemoteArtistsResult[T: RemoteArtist](CountResult):
    artists: Annotated[Sequence[T], TO_TUPLE, *_log_formatters] = Field(
        description="The artists in this result.",
        default_factory=tuple
    )

    @computed_field(description="All available albums by the artists.")
    @property
    def albums(self) -> Annotated[tuple[RemoteAlbum[Any, T, Any], ...], *_log_formatters]:
        return tuple(
            album for artist in self.artists if isinstance(artist, RemoteArtistCollection) for album in artist.albums
        )

    @computed_field(description="All available tracks in the albums by the artists.")
    @property
    def tracks(self) -> Annotated[tuple[RemoteTrack[Any, T, Any, Any], ...], *_log_formatters]:
        return tuple(
            track for album in self.albums if isinstance(album, RemoteAlbumCollection) for track in album.tracks
        )


class RemoteAlbumsResult[T: RemoteAlbum](CountResult):
    albums: Annotated[Sequence[T], TO_TUPLE, *_log_formatters] = Field(
        description="The albums in this result.",
        default_factory=tuple,
    )

    @computed_field(description="All available tracks on the albums.")
    @property
    def tracks(self) -> Annotated[tuple[RemoteTrack[Any, Any, T, Any], ...], *_log_formatters]:
        return tuple(
            track for album in self.albums if isinstance(album, RemoteAlbumCollection) for track in album.tracks
        )

    @computed_field(description="All available artists featured on the albums.")
    @property
    def artists(self) -> Annotated[tuple[RemoteArtist, ...], *_log_formatters]:
        return tuple(artist for album in self.albums for artist in album.artists)
