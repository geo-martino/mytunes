from collections.abc import MutableMapping, Sequence
from typing import ClassVar, Any, Self, final

from pydantic import Field, model_validator, ModelWrapValidatorHandler

from musify._types import StrippedString
from musify.exception import MusifyValueError
from musify.local.collection._base import LocalCollection
from musify.local.item.track import LocalTrack, HasLocalTracks
from musify.models.properties.length import HasLength
from musify.models.properties.name import HasName
from musify.models.properties.uri import URI


@final
class Folder[TT: LocalTrack](LocalCollection[TT], HasLocalTracks[URI, TT], HasName, HasLength):
    """Represents a folder collection and its properties."""
    __final__ = True

    type: ClassVar[str] = "folder"

    name: StrippedString = Field(
        description="The name of this folder.",
        default=None,
        alias="folder",
    )

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
        if not all(isinstance(track, LocalTrack) for track in tracks):
            return handler(data)

        names = {track.folder for track in tracks}
        if len(names) == 0:  # This shouldn't happen, but just in case
            raise MusifyValueError("No folder given and no folders found in tracks")
        if len(names) > 1:
            raise MusifyValueError(
                f"No folder given and tracks are from different folders: {", ".join(map(str, names))}"
            )

        data[key] = names.pop()
        return handler(data)

    # noinspection PyNestedDecorators
    @model_validator(mode="wrap")
    @classmethod
    def _filter_tracks_on_folder_name(
            cls, data: MutableMapping[str, Any], handler: ModelWrapValidatorHandler[Self]
    ) -> Self:
        if not isinstance(data, MutableMapping):
            return handler(data)
        if not isinstance(tracks := data.get(key := "tracks"), Sequence):
            return handler(data)
        if not isinstance(name := data.get("name"), str) or not name.strip():
            return handler(data)

        data[key] = [track for track in tracks if track.folder == name]
        return handler(data)

    # noinspection PyNestedDecorators
    @model_validator(mode="after")
    def _check_tracks_are_from_same_folder(self) -> Self:
        if not self.tracks:
            return self

        names = {track.folder for track in self.tracks}
        if len(names) > 1:
            raise MusifyValueError(f"Tracks are from different folders: {", ".join(map(str, names))}")

        return self.tracks

    @property
    def compilation(self) -> bool:
        """The folder is considered a compilation if over 50% of tracks are marked as compilation."""
        compilation_iter = (track.album.compilation is True for track in self.tracks if track.album is not None)
        return (sum(compilation_iter) / len(self.tracks)) > 0.5
