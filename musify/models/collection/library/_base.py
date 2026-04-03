from abc import abstractmethod
from typing import Any, ClassVar

from pydantic import Field

from musify.models import ResourceModel
from musify.models._metaclass import makecls
from musify.models.collection import CollectionModel
from musify.models.collection.playlist import Playlist, HasPlaylists, HasMutablePlaylists
from musify.models.item.track import Track, HasTracks, HasMutableTracks
from musify.models.properties.asynch import HasAsyncOperations
from musify.models.properties.logger import HasLogger
from musify.processors.filters.composite import IncludeExcludeFilter
from musify.processors.filters.values import NameFilter


class HasTracksAndPlaylists[TK, TV: Track, KP, VP: Playlist](
    CollectionModel[TV], HasTracks[TK, TV], HasPlaylists[KP, VP],
):
    @property
    def _items(self) -> list[TV]:
        return list(self.tracks)

    def dump(self) -> dict[str, Any]:
        """Generate a dump of this library's state. This can be used for backup or debugging purposes."""
        return self.model_dump(mode="json", exclude_none=True)


# noinspection PyAbstractClass
class Library[TK, TV: Track, KP, VP: Playlist](
    ResourceModel, HasTracksAndPlaylists[TK, TV, KP, VP], HasAsyncOperations, HasLogger, metaclass=makecls()
):
    """A library of tracks and playlists and other object types."""
    type: ClassVar[str] = "library"

    source: ClassVar[str] = Field(
        description="The name of the source of this library.",
    )

    playlist_filter: NameFilter | IncludeExcludeFilter[VP, NameFilter, NameFilter] | None = Field(
        description="The filter to apply when loading playlists. Filters playlist by name.",
        default=None,
        repr=False,
    )

    @abstractmethod
    async def load(self):
        """Loads all resources in this library and log results. Replaces all loaded resources."""
        raise NotImplementedError

    @abstractmethod
    async def load_tracks(self) -> Any:
        """Loads all tracks available for this library. Replaces all currently loaded tracks."""
        raise NotImplementedError

    @abstractmethod
    def log_tracks(self) -> None:
        """Log stats on currently loaded tracks"""
        raise NotImplementedError

    @abstractmethod
    async def load_playlists(self) -> Any:
        """
        Load all playlists available for this library filtered down using the ``playlist_filter`` if given.
        Replaces all currently loaded playlists.
        """
        raise NotImplementedError

    @abstractmethod
    def log_playlists(self) -> None:
        """Log stats on currently loaded playlists"""
        raise NotImplementedError


# noinspection PyAbstractClass
class MutableLibrary[TK, TV: Track, KP, VP: Playlist](
    HasMutableTracks[TK, TV], HasMutablePlaylists[KP, VP], Library[TK, TV, KP, VP]
):
    """A mutable library of tracks and playlists and other object types."""
