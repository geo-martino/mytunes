from collections.abc import MutableMapping, Sequence
from typing import Any, Self

from pydantic import model_validator

from musify.exception import MusifyValueError
from musify.models.item.genre import Genre
from musify.models.item.track import Track, HasTracks
from musify.models.properties.length import HasLength


class GenreCollection[TK, TV: Track](Genre, HasTracks[TK, TV], HasLength):
    """Represents a genre collection and its properties."""
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

        names = {genre.name for track in tracks for genre in track.genres}
        if len(names) == 0:
            raise MusifyValueError("No genre given and no genres found in tracks")
        if len(names) > 1:
            raise MusifyValueError(
                f"No genre given and tracks are from different genres: {", ".join(map(str, names))}"
            )

        data[key] = names.pop()
        return data

    # noinspection PyNestedDecorators
    @model_validator(mode="before")
    @staticmethod
    def _filter_tracks_on_genre_name(data: MutableMapping[str, Any]) -> Any:
        if not isinstance(data, MutableMapping):
            return data
        if not isinstance(tracks := data.get(key := "tracks"), Sequence):
            return data
        if not isinstance(name := data.get("name"), str) or not name.strip():
            return data

        data[key] = [track for track in tracks if any(genre.name == name for genre in track.genres)]
        return data

    # noinspection PyNestedDecorators
    @model_validator(mode="after")
    def _check_tracks_are_from_same_genre(self) -> Self:
        if not self.tracks:
            return self

        for track in self.tracks:
            names = {genre.name for genre in track.genres}
            if self.name not in names:
                raise MusifyValueError(f"Track does not contain the genre {self.name!r}: {", ".join(map(str, names))}")

        return self
