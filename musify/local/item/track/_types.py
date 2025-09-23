from typing import Annotated

from pydantic import Field

from musify.local.item.track.flac import FLAC
from musify.local.item.track.m4a import M4A
from musify.local.item.track.mp3 import MP3
from musify.local.item.track.wma import WMA

type LocalTrackType = Annotated[
    MP3 | FLAC | M4A | WMA,
    Field(discriminator="format")
]
