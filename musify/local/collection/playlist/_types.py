from typing import Annotated

from pydantic import Field

from musify.local.collection.playlist.m3u import M3U
from musify.local.collection.playlist.xautopf import XAutoPF

type LocalPlaylistType = Annotated[
    M3U | XAutoPF,
    Field(discriminator="format")
]
