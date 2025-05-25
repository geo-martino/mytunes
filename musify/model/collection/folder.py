from typing import ClassVar

from pydantic import Field

from musify._types import StrippedString
from musify.model.item.track import Track, HasTracks
from musify.model.properties.length import HasLength
from musify.model.properties.name import HasName


class Folder[TK, TV: Track](HasTracks[TK, TV], HasName, HasLength):
    """Represents a folder collection and its properties."""
    type: ClassVar[str] = "folder"

    name: StrippedString = Field(
        description="The name of this folder.",
        alias="folder",
    )

    @property
    def compilation(self) -> bool:
        """The folder is considered a compilation if over 50% of tracks are marked as compilation."""
        compilation_iter = (track.album.compilation is True for track in self.tracks if track.album is not None)
        return (sum(compilation_iter) / len(self.tracks)) > 0.5
