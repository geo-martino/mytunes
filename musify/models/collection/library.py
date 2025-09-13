"""
The core abstract implementations of :py:class:`MusifyItem` and :py:class:`MusifyCollection` classes.
"""
import itertools
from abc import ABCMeta, abstractmethod
from collections.abc import Collection, Mapping, Iterator
from typing import ClassVar

from pydantic import Field

from musify.models.collection.playlist import Playlist, HasPlaylists, HasMutablePlaylists
from musify.models.item.track import Track, HasTracks, HasMutableTracks

type LibraryMergeType[T] = Library[T] | Collection[Playlist[T]] | Mapping[str, Playlist[T]]


class _HasTracksAndPlaylistsMixin[TK, TV: Track, KP, VP: Playlist](HasTracks[TK, TV], HasPlaylists[KP, VP]):
    @property
    def tracks_in_playlists(self) -> list[TV]:
        """All unique tracks from all playlists in this library"""
        def _playlist_tracks_in_tracks(playlist: VP) -> Iterator[TV]:
            return (track for track in playlist.tracks if track not in self.tracks)
        return list(itertools.chain.from_iterable(map(_playlist_tracks_in_tracks, self.playlists.values())))


class Library[TK, TV: Track, KP, VP: Playlist](_HasTracksAndPlaylistsMixin[TK, TV, KP, VP], metaclass=ABCMeta):
    """A library of tracks and playlists and other object types."""
    type: ClassVar[str] = "library"

    source: ClassVar[str] = Field(
        description="The name of the source of this library.",
    )

    @abstractmethod
    async def load(self):
        """Implementations of this function should load all data for this library and log results."""
        raise NotImplementedError

    @abstractmethod
    async def load_tracks(self) -> None:
        """
        Implementations of this function should load all tracks for this library
        and store them within the library object to be retrieved with property ``tracks``.
        """
        raise NotImplementedError

    @abstractmethod
    def log_tracks(self) -> None:
        """Log stats on currently loaded tracks"""
        raise NotImplementedError

    @abstractmethod
    async def load_playlists(self) -> None:
        """
        Implementations of this function should load all playlists for this library
        and store them within the library object to be retrieved with property ``playlists``.
        """
        raise NotImplementedError

    @abstractmethod
    def log_playlists(self) -> None:
        """Log stats on currently loaded playlists"""
        raise NotImplementedError


class MutableLibrary[TK, TV: Track, KP, VP: Playlist](
    Library[TK, TV, KP, VP], HasMutableTracks[TK, TV], HasMutablePlaylists[TK, VP], metaclass=ABCMeta
):
    """A mutable library of tracks and playlists and other object types."""
