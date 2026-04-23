from collections.abc import MutableMapping, Sequence
from typing import ClassVar, Any, Self, final, Annotated

from pydantic import Field, model_validator

from mytunes._types import StrippedString
from mytunes.core.properties.length import HasLength
from mytunes.core.properties.name import HasName
from mytunes.core.properties.uri import URI
from mytunes.core.sequence import UniqueSequence
from mytunes.exception import MyTunesValidationError
from mytunes.local._collection._base import LocalCollection
from .._item.track import LocalTrack, HasLocalTracks
from ..._base.attribute import Attribute


@final
class Folder[TT: LocalTrack](HasLocalTracks[TT], LocalCollection[TT], HasName, HasLength):
    """Represents a folder collection and its properties."""
    __final__ = True

    type: ClassVar[str] = "folder"

    name: Annotated[StrippedString, Attribute()] = Field(
        description="The name of this folder.",
        default=None,
        alias="folder",
    )

    @property
    def _items(self) -> UniqueSequence[TT]:
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
        if not all(isinstance(track, LocalTrack) for track in tracks):
            return data

        names = {track.folder for track in tracks}
        if len(names) == 0:  # This shouldn't happen, but just in case
            raise MyTunesValidationError("No folder given and no folders found in tracks")
        if len(names) > 1:
            raise MyTunesValidationError(
                f"No folder given and tracks are from different folders: {", ".join(map(str, names))}"
            )

        data[key] = names.pop()
        return data

    @model_validator(mode="before")
    @classmethod
    def _filter_tracks_on_folder_name[T](cls, data: T | MutableMapping[str, Any]) -> T | MutableMapping[str, Any]:
        if not isinstance(data, MutableMapping):
            return data
        if not isinstance(tracks := data.get(key := "tracks"), Sequence):
            return data
        if not isinstance(name := data.get("name"), str) or not name.strip():
            return data

        data[key] = [track for track in tracks if track.folder == name]
        return data

    @model_validator(mode="after")
    def _check_tracks_are_from_same_folder(self) -> Self:
        if not self.tracks:
            return self

        names = {track.folder for track in self.tracks}
        if len(names) > 1:
            raise MyTunesValidationError(f"Tracks are from different folders: {", ".join(map(str, names))}")

        return self.tracks

    @property
    def compilation(self) -> bool:
        """The folder is considered a compilation if over 50% of tracks are marked as compilation."""
        compilation_iter = (track.album.compilation is True for track in self.tracks if track.album is not None)
        return (sum(compilation_iter) / len(self.tracks)) > 0.5
