from functools import total_ordering
from typing import Any, Annotated

import mutagen
from pydantic import Field, PositiveInt, PositiveFloat, model_validator, ConfigDict

from musify._models import AttributeModel
from musify._models.metadata import Attribute
from musify._models.properties._core import NumberModel
from musify._models.properties.length import HasLength


@total_ordering
class Decibels(NumberModel[Annotated[float, Field(ge=-60.0, le=0.0)]]):
    """Represents a decibel value for an audio file."""

    def __str__(self):
        return f"{round(self.root, 2)} dB"


# noinspection PyAbstractClass
class AudioProperties(HasLength):
    """Attributes and operations for an audio on a filesystem."""
    model_config = ConfigDict(frozen=True)

    channels: Annotated[PositiveInt | None, Attribute()] = Field(
        description="The number of channels in this audio file i.e. 1 for mono, 2 for stereo, ...",
        default=None,
        frozen=True,
    )
    bit_rate: Annotated[PositiveFloat | None, Attribute()] = Field(
        description="The bit rate of this track in kbps",
        default=None,
        frozen=True,
    )
    bit_depth: Annotated[PositiveInt | None, Attribute()] = Field(
        description="The bit depth of this track in bits",
        default=None,
        frozen=True,
    )
    sample_rate: Annotated[PositiveFloat | None, Attribute()] = Field(
        description="The sample rate of the audio file, in kHz.",
        default=None,
        frozen=True,
    )

    @model_validator(mode="before")
    @classmethod
    def _from_mutagen[T](cls, data: T | mutagen.FileType) -> T | dict[str, Any]:
        if not isinstance(data, mutagen.FileType):
            return data

        file = data
        try:
            bit_depth = file.info.bits_per_sample
        except AttributeError:  # not all mutagen file types provide this info
            bit_depth = None

        data = dict(
            length=file.info.length,
            channels=file.info.channels,
            bit_rate=file.info.bitrate / 1000,  # convert to bps to kbps
            bit_depth=bit_depth,
            sample_rate=file.info.sample_rate / 1000,  # convert to Hz to kHz
        )
        return data


class HasAudioProperties(AttributeModel):
    audio: Annotated[AudioProperties, Attribute()] = Field(
        description="The audio properties of the file.",
        default_factory=AudioProperties,
        frozen=True,
    )

    @classmethod
    def _extract_tags_from_mutagen(cls, file: mutagen.FileType) -> dict[str, Any]:
        return dict(audio=file)
