from collections.abc import Sequence, MutableMapping
from typing import Self, Any

from pydantic import model_validator

from musify.exception import MusifyValueError
from musify.models.item.album import Album
from musify.models.item.artist import Artist
from musify.models.item.genre import Genre
from musify.models.item.track import Track, HasTracks


class AlbumCollection[TK, TV: Track, RT: Artist, GT: Genre](Album[RT, GT], HasTracks[TK, TV]):
    # noinspection PyNestedDecorators
    @model_validator(mode="before")
    @staticmethod
    def _get_name_from_tracks(data: MutableMapping[str, Any]) -> Any:
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
            raise MusifyValueError("No album name given and no album names found in tracks")
        if len(names) > 1:
            raise MusifyValueError(
                f"No album name given and tracks are from different albums: {", ".join(map(str, names))}"
            )

        data[key] = names.pop()
        return data

    # noinspection PyNestedDecorators
    @model_validator(mode="before")
    @staticmethod
    def _filter_tracks_on_album_name(data: MutableMapping[str, Any]) -> Any:
        if not isinstance(data, MutableMapping):
            return data
        if not isinstance(tracks := data.get(key := "tracks"), Sequence):
            return data
        if not isinstance(name := data.get("name"), str) or not name.strip():
            return data

        data[key] = [track for track in tracks if track.album is not None and track.album.name == name]
        return data

    # noinspection PyNestedDecorators
    @model_validator(mode="after")
    def _check_tracks_are_from_same_album(self) -> Self:
        if not self.tracks:
            return self

        names = {track.album.name if track.album is not None else None for track in self.tracks}
        if len(names) > 1:
            raise MusifyValueError(f"Tracks are from different albums: {", ".join(map(str, names))}")

        return self.tracks
