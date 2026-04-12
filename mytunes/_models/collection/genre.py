from collections.abc import MutableMapping, Sequence
from typing import Any, Self

from pydantic import model_validator, validate_call

from mytunes._models.api import CollectionReadEndpoints
from mytunes._models.api.items import HasGenreEndpoints
from mytunes._models.collection._base import RemoteCollection, CollectionModel
from mytunes._models.cursors import PageCursor
from mytunes._models.exception import MyTunesValidationError
from mytunes._models.item.genre import Genre, RemoteGenre
from mytunes._models.item.track import Track, HasTracks, RemoteTrack
from mytunes._models.properties.length import HasLength
from mytunes._models.properties.uri import URI
from mytunes._models.sequence import UniqueSequence


class GenreCollection[TK, TV: Track](CollectionModel[TV], HasTracks[TK, TV], Genre, HasLength):
    """Represents a genre collection and its properties."""

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

        names = {genre.name for track in tracks for genre in track.genres}
        if len(names) == 0:
            raise MyTunesValidationError("No genre given and no genres found in tracks")
        if len(names) > 1:
            raise MyTunesValidationError(
                f"No genre given and tracks are from different genres: {", ".join(map(str, names))}"
            )

        data[key] = names.pop()
        return data

    @model_validator(mode="before")
    @classmethod
    def _filter_tracks_on_genre_name[T](cls, data: T | MutableMapping[str, Any]) -> T | MutableMapping[str, Any]:
        if not isinstance(data, MutableMapping):
            return data
        if not isinstance(tracks := data.get(key := "tracks"), Sequence):
            return data
        if not isinstance(name := data.get("name"), str) or not name.strip():
            return data

        data[key] = [track for track in tracks if any(genre.name == name for genre in track.genres)]
        return data

    @model_validator(mode="after")
    def _check_tracks_are_from_same_genre(self) -> Self:
        if not self.tracks:
            return self

        for track in self.tracks:
            names = {genre.name for genre in track.genres}
            if self.name not in names:
                raise MyTunesValidationError(
                    f"Track does not contain the genre {self.name!r}: {", ".join(map(str, names))}"
                )

        return self


class RemoteGenreCollection[UT: URI, TT: RemoteTrack, CT: PageCursor](
    GenreCollection[UT, TT],
    RemoteGenre[UT],
    RemoteCollection[UT, TT,  CT],
):
    def _clear(self) -> None:
        # noinspection PyProtectedMember
        self.tracks._replace(())

    @validate_call
    async def extend(self, api: HasGenreEndpoints[CollectionReadEndpoints]) -> None:
        # noinspection PyProtectedMember
        self.tracks._replace(await api.genres.get_all(self))
