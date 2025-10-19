from typing import Any

import mutagen
from pydantic import Field, PositiveInt, PositiveFloat

from musify.models.properties.file import IsFile
from musify.models.properties.length import HasLength


class IsAudioFile(HasLength, IsFile):
    """Attributes and operations for an audio on a filesystem."""

    channels: PositiveInt | None = Field(
        description="The number of channels in this audio file i.e. 1 for mono, 2 for stereo, ...",
        default=None,
    )
    bit_rate: PositiveFloat | None = Field(
        description="The bit rate of this track in kbps",
        default=None,
    )
    bit_depth: PositiveInt | None = Field(
        description="The bit depth of this track in bits",
        default=None,
    )
    sample_rate: PositiveFloat | None = Field(
        description="The sample rate of the audio file, in kHz.",
        default=None,
    )

    @classmethod
    def extract_tags_from_mutagen(cls, file: mutagen.FileType) -> dict[str, Any]:
        """Extract the tags from a mutagen file object."""
        try:
            bit_depth = file.info.bits_per_sample
        except AttributeError:
            bit_depth = None

        data = super().extract_tags_from_mutagen(file)
        data |= dict(
            length=file.info.length,
            channels=file.info.channels,
            bit_rate=file.info.bitrate / 1000,  # convert to bps to kbps
            bit_depth=bit_depth,
            sample_rate=file.info.sample_rate / 1000,  # convert to Hz to kHz
        )
        return data
