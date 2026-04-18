from collections.abc import Sequence, MutableMapping
from typing import Self, Any

from pydantic import model_validator, computed_field, PositiveInt, validate_call

from mytunes._models.api import CollectionReadEndpoints
from mytunes._models.api.items import HasAlbumEndpoints
from mytunes._models.collection._base import RemoteCollection, CollectionModel
from mytunes._models.cursors import PageCursor
from mytunes._models.item.album import Album, RemoteAlbum
from mytunes._models.item.artist import Artist, RemoteArtist
from mytunes._models.item.genre import Genre, RemoteGenre
from mytunes._models.item.track import Track, HasTracks, RemoteTrack
from mytunes._models.properties.uri import URI
from mytunes._models.sequence import UniqueSequence
from mytunes.exception import MyTunesValidationError


class AlbumCollection[TK, TV: Track, RT: Artist, GT: Genre](CollectionModel[TV], HasTracks[TK, TV], Album[RT, GT]):

    @property
    def _items(self) -> UniqueSequence[TK, TV]:
        return self.tracks

    @model_validator(mode="before")
    @classmethod
    def _get_name_from_tracks[T](cls, data: T | MutableMapping[str, Any]) -> T | MutableMapping[str, Any]:
        if not isinstance(data, MutableMapping):
            return data
        if isinstance(name := data.get(key := "name"), str) and name.strip():
            return data

        if not isinstance(tracks := data.get("tracks", []), Sequence):
            return data
        if not all(isinstance(track, Track) for track in tracks):
            return data

        names = {track.album.name if track.album is not None else None for track in tracks}
        if len(names) == 0:
            raise MyTunesValidationError("No album name given and no album names found in tracks")
        if len(names) > 1:
            raise MyTunesValidationError(
                f"No album name given and tracks are from different albums: {", ".join(map(str, names))}"
            )

        data[key] = names.pop()
        return data

    @model_validator(mode="before")
    @classmethod
    def _filter_tracks_on_album_name[T](cls, data: T | MutableMapping[str, Any]) -> T | MutableMapping[str, Any]:
        if not isinstance(data, MutableMapping):
            return data
        if not isinstance(tracks := data.get(key := "tracks"), Sequence):
            return data
        if not isinstance(name := data.get("name"), str) or not name.strip():
            return data

        data[key] = [track for track in tracks if track.album is not None and track.album.name == name]
        return data

    @model_validator(mode="after")
    def _check_tracks_are_from_same_album(self) -> Self:
        if not self.tracks:
            return self

        names = {track.album.name if track.album is not None else None for track in self.tracks}
        if len(set(filter(None, names))) > 1:
            raise MyTunesValidationError(f"Tracks are from different albums: {", ".join(map(str, names))}")

        return self


class RemoteAlbumCollection[UT: URI, TT: RemoteTrack, RT: RemoteArtist, GT: RemoteGenre, CT: PageCursor](
    AlbumCollection[UT, TT, RT, GT],
    RemoteAlbum[URI, RT, GT],
    RemoteCollection[UT, TT, CT],
):
    @computed_field(description="The total number of tracks in this album")
    @property
    def track_total(self) -> PositiveInt | None:
        return self.cursor.total

    def _clear(self) -> None:
        # noinspection PyProtectedMember
        self.tracks._replace(())

    @validate_call
    async def extend(self, api: HasAlbumEndpoints[CollectionReadEndpoints]) -> None:
        # noinspection PyProtectedMember
        self.tracks._replace(await api.albums.get_all(self))
