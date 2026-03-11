from collections.abc import Sequence, MutableMapping
from typing import Self, Any

from pydantic import model_validator, ModelWrapValidatorHandler

from musify.exception import MusifyValueError
from musify.models.remote import RemoteResource
from musify.models.collection._base import ItemsCursor, RemoteCollection
from musify.models.item.album import Album, RemoteAlbum
from musify.models.item.artist import Artist, RemoteArtist
from musify.models.item.genre import Genre, RemoteGenre
from musify.models.item.track import Track, HasTracks, RemoteTrack
from musify.models.properties.uri import URI


class AlbumCollection[TK, TV: Track, RT: Artist, GT: Genre, UT: URI](HasTracks[TK, TV], Album[RT, GT, UT]):
    # noinspection PyNestedDecorators
    @model_validator(mode="wrap")
    @classmethod
    def _get_name_from_tracks(cls, data: MutableMapping[str, Any], handler: ModelWrapValidatorHandler[Self]) -> Self:
        if not isinstance(data, MutableMapping):
            return handler(data)
        if isinstance(name := data.get(key := "name"), str) and name.strip():
            return handler(data)

        if not isinstance(tracks := data.get("tracks", []), Sequence):
            return handler(data)
        if not all(isinstance(track, Track) for track in tracks):
            return handler(data)

        names = {track.album.name if track.album is not None else None for track in tracks}
        if len(names) == 0:
            raise MusifyValueError("No album name given and no album names found in tracks")
        if len(names) > 1:
            raise MusifyValueError(
                f"No album name given and tracks are from different albums: {", ".join(map(str, names))}"
            )

        data[key] = names.pop()
        return handler(data)

    # noinspection PyNestedDecorators
    @model_validator(mode="wrap")
    @classmethod
    def _filter_tracks_on_album_name(
            cls, data: MutableMapping[str, Any], handler: ModelWrapValidatorHandler[Self]
    ) -> Self:
        if not isinstance(data, MutableMapping):
            return handler(data)
        if not isinstance(tracks := data.get(key := "tracks"), Sequence):
            return handler(data)
        if not isinstance(name := data.get("name"), str) or not name.strip():
            return handler(data)

        data[key] = [track for track in tracks if track.album is not None and track.album.name == name]
        return handler(data)

    # noinspection PyNestedDecorators
    @model_validator(mode="after")
    def _check_tracks_are_from_same_album(self) -> Self:
        if not self.tracks:
            return self

        names = {track.album.name if track.album is not None else None for track in self.tracks}
        if len(set(filter(lambda x: x is not None, names))) > 1:
            raise MusifyValueError(f"Tracks are from different albums: {", ".join(map(str, names))}")

        return self


class RemoteAlbumCollection[TT: RemoteTrack, RT: RemoteArtist, GT: RemoteGenre, UT: URI, CT: ItemsCursor](
    AlbumCollection[UT, TT, RT, GT, UT],
    RemoteAlbum[UT, RT, GT],
    RemoteResource[UT],
    RemoteCollection[TT, CT],
):
    pass
