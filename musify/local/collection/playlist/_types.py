from typing import Annotated, Union

from pydantic import Field, Discriminator

from musify.local.collection.playlist.m3u import M3U
from musify.local.collection.playlist.xautopf import XAutoPF
from musify.models.properties.file import IsLocalFile

_playlist_classes = (M3U, XAutoPF)
type LocalPlaylistType = Annotated[
    Union[*(cls.get_annotation_from_supported_extensions() for cls in _playlist_classes)],
    Field(discriminator=Discriminator(IsLocalFile.get_ext_from_input)),
]
