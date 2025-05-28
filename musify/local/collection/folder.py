from collections.abc import MutableMapping, Sequence
from typing import ClassVar, Any, Self

from pydantic import Field, model_validator

from musify._types import StrippedString
from musify.exception import MusifyValueError
from musify.local.item.track import LocalTrack
from musify.model.item.track import HasTracks
from musify.model.properties.length import HasLength
from musify.model.properties.name import HasName


class Folder[TK, TV: LocalTrack](HasTracks[TK, TV], HasName, HasLength):
    """Represents a folder collection and its properties."""
    type: ClassVar[str] = "folder"

    name: StrippedString = Field(
        description="The name of this folder.",
        default=None,
        alias="folder",
    )

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
        if not all(isinstance(track, LocalTrack) for track in tracks):
            return data

        names = {track.folder for track in tracks}
        if len(names) == 0:  # This shouldn't happen, but just in case
            raise MusifyValueError("No folder given and no folders found in tracks")
        if len(names) > 1:
            raise MusifyValueError(
                f"No folder given and tracks are from different folders: {", ".join(map(str, names))}"
            )

        data[key] = names.pop()
        return data

    # noinspection PyNestedDecorators
    @model_validator(mode="before")
    @staticmethod
    def _filter_tracks_on_folder_name(data: MutableMapping[str, Any]) -> Any:
        if not isinstance(data, MutableMapping):
            return data
        if not isinstance(tracks := data.get(key := "tracks"), Sequence):
            return data
        if not isinstance(name := data.get("name"), str) or not name.strip():
            return data

        data[key] = [track for track in tracks if track.folder == name]
        return data

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
