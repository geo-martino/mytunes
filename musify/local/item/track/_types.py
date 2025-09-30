from pathlib import Path
from typing import Annotated, Any, Union

import mutagen
from pydantic import Field, Discriminator

from musify.local.item.track.flac import FLAC
from musify.local.item.track.m4a import M4A
from musify.local.item.track.mp3 import MP3
from musify.local.item.track.wma import WMA
from musify.models.properties.file import IsFile


def _get_format(value: Any) -> str | None:
    if isinstance(value, mutagen.FileType):
        value = Path(value.filename)
    return IsFile.get_ext_from_input(value)


_track_classes = (MP3, FLAC, M4A, WMA)
type LocalTrackType = Annotated[
    Union[*(cls.get_annotation_from_supported_extensions() for cls in _track_classes)],
    Field(discriminator=Discriminator(_get_format)),
]
