from collections.abc import MutableMapping, Sequence
from typing import Any, Self, TYPE_CHECKING

from pydantic import model_validator, ModelWrapValidatorHandler

from musify.exception import MusifyValueError
from musify.models.collection._base import RemoteCollection
from musify.models.cursors import PageCursor
from musify.models.item.genre import Genre, RemoteGenre
from musify.models.item.track import Track, HasTracks, RemoteTrack
from musify.models.properties.length import HasLength
from musify.models.properties.uri import URI
from musify.models.remote import RemoteResource

if TYPE_CHECKING:
    from musify.models.api.genre import HasGenreEndpoints, GenreReadCollectionEndpoints


class GenreCollection[TK, TV: Track](Genre, HasTracks[TK, TV], HasLength):
    """Represents a genre collection and its properties."""
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

        names = {genre.name for track in tracks for genre in track.genres}
        if len(names) == 0:
            raise MusifyValueError("No genre given and no genres found in tracks")
        if len(names) > 1:
            raise MusifyValueError(
                f"No genre given and tracks are from different genres: {", ".join(map(str, names))}"
            )

        data[key] = names.pop()
        return handler(data)

    # noinspection PyNestedDecorators
    @model_validator(mode="wrap")
    @classmethod
    def _filter_tracks_on_genre_name(
            cls, data: MutableMapping[str, Any], handler: ModelWrapValidatorHandler[Self]
    ) -> Self:
        if not isinstance(data, MutableMapping):
            return handler(data)
        if not isinstance(tracks := data.get(key := "tracks"), Sequence):
            return handler(data)
        if not isinstance(name := data.get("name"), str) or not name.strip():
            return handler(data)

        data[key] = [track for track in tracks if any(genre.name == name for genre in track.genres)]
        return handler(data)

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


class RemoteGenreCollection[UT: URI, TT: RemoteTrack, CT: PageCursor](
    GenreCollection[UT, TT],
    RemoteGenre[UT],
    RemoteResource[UT],
    RemoteCollection[TT, CT],
):
    # @validate_call  # can't validate as can't import these types at runtime due to cyclical imports
    async def extend(self, api: HasGenreEndpoints[GenreReadCollectionEndpoints]) -> None:
        # noinspection PyProtectedMember
        self.tracks._replace(await api.genres.get_all(self))
