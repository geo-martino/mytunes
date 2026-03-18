from functools import total_ordering
from typing import Any, Annotated

import mutagen
from pydantic import Field, PositiveInt, PositiveFloat

from musify.models._metadata import Attribute
from musify.models.properties._core import NumberModel
from musify.models.properties.file import IsFile
from musify.models.properties.length import HasLength


@total_ordering
class Decibels(NumberModel[Annotated[float, Field(ge=-60.0, le=0.0)]]):
    """Represents a decibel value for an audio file."""

    def __str__(self):
        return f"{round(self.root, 2)} dB"


# noinspection PyAbstractClass
class IsAudioFile(HasLength, IsFile):
    """Attributes and operations for an audio on a filesystem."""

    channels: Annotated[PositiveInt | None, Attribute()] = Field(
        description="The number of channels in this audio file i.e. 1 for mono, 2 for stereo, ...",
        default=None,
    )
    bit_rate: Annotated[PositiveFloat | None, Attribute()] = Field(
        description="The bit rate of this track in kbps",
        default=None,
    )
    bit_depth: Annotated[PositiveInt | None, Attribute()] = Field(
        description="The bit depth of this track in bits",
        default=None,
    )
    sample_rate: Annotated[PositiveFloat | None, Attribute()] = Field(
        description="The sample rate of the audio file, in kHz.",
        default=None,
    )

    @classmethod
    def _extract_tags_from_mutagen(cls, file: mutagen.FileType) -> dict[str, Any]:
        """Extract the tags from a mutagen file object."""
        try:
            bit_depth = file.info.bits_per_sample
        except AttributeError:
            bit_depth = None

        data = dict(
            length=file.info.length,
            channels=file.info.channels,
            bit_rate=file.info.bitrate / 1000,  # convert to bps to kbps
            bit_depth=bit_depth,
            sample_rate=file.info.sample_rate / 1000,  # convert to Hz to kHz
        )
        return data
