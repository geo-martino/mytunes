"""
The core abstract implementations of :py:class:`MusifyItem` and :py:class:`MusifyCollection` classes.
"""
import itertools
from abc import abstractmethod
from collections.abc import Iterator
from typing import ClassVar

from pydantic import Field

from musify.models.collection.playlist import Playlist, HasPlaylists, HasMutablePlaylists
from musify.models.item.track import Track, HasTracks, HasMutableTracks
from musify.models.properties.logger import HasLogger
from musify.processors_new.filters import ValuesFilter


class HasTracksAndPlaylists[TK, TV: Track, KP, VP: Playlist](HasTracks[TK, TV], HasPlaylists[KP, VP]):
    @property
    def tracks_in_playlists(self) -> list[TV]:
        """All unique tracks from all playlists in this library"""
        def _playlist_tracks_in_tracks(playlist: VP) -> Iterator[TV]:
            return (track for track in playlist.tracks if track not in self.tracks)
        return list(itertools.chain.from_iterable(map(_playlist_tracks_in_tracks, self.playlists.values())))


# noinspection PyAbstractClass
class Library[TK, TV: Track, KP, VP: Playlist](
    HasTracksAndPlaylists[TK, TV, KP, VP], HasLogger
):
    """A library of tracks and playlists and other object types."""
    type: ClassVar[str] = "library"

    source: ClassVar[str] = Field(
        description="The name of the source of this library.",
    )

    playlist_filter: ValuesFilter[str] | None = Field(
        description="The filter to apply when loading playlists. Filters playlist by name.",
        default=None
    )

    @abstractmethod
    async def load(self):
        """Loads all resources in this library and log results. Replaces all loaded resources."""
        raise NotImplementedError

    @abstractmethod
    async def load_tracks(self) -> None:
        """Loads all tracks available for this library. Replaces all currently loaded tracks."""
        raise NotImplementedError

    @abstractmethod
    def log_tracks(self, skip_log: bool = False) -> tuple[str, ...]:
        """Log stats on currently loaded tracks"""
        raise NotImplementedError

    @abstractmethod
    async def load_playlists(self) -> None:
        """
        Load all playlists available for this library filtered down using the ``playlist_filter`` if given.
        Replaces all currently loaded playlists.
        """
        raise NotImplementedError

    @abstractmethod
    def log_playlists(self, skip_log: bool = False) -> list[tuple[str, ...]]:
        """Log stats on currently loaded playlists"""
        raise NotImplementedError


# noinspection PyAbstractClass
class MutableLibrary[TK, TV: Track, KP, VP: Playlist](
    HasMutableTracks[TK, TV], HasMutablePlaylists[KP, VP], Library[TK, TV, KP, VP]
):
    """A mutable library of tracks and playlists and other object types."""
