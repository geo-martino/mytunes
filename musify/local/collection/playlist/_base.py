from abc import ABCMeta

from pydantic import Field

from musify.local.collection._base import LocalCollection
from musify.local.item.track import LocalTrack
from musify.model.collection.playlist import Playlist
from musify.model.properties.file import IsFile, PathMapper


class LocalPlaylist[TK, TV: LocalTrack](LocalCollection, Playlist[TK, TV], IsFile, metaclass=ABCMeta):
    path_mapper: PathMapper = Field(
        description="Mapper to use when mapping paths stored in the playlist file.",
        default_factory=PathMapper,
    )
