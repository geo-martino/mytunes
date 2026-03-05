import asyncio
from collections import Counter
from collections.abc import Sequence, Collection
from pathlib import Path
from typing import Self, final as final_decorator

from pydantic import Field, TypeAdapter

from musify.local.collection.playlist import LocalPlaylist
from musify.local.item.track import LocalTrack
from musify.processors_new import Result
from musify.processors_new.filters import PathsFilter


class SyncResultM3U(Result):
    """Stores the results of a sync with a local M3U playlist"""
    start: int = Field(
        description="The total number of tracks in the playlist before the sync.",
    )
    added: int = Field(
        description="The number of tracks added to the playlist.",
    )
    removed: int = Field(
        description="The number of tracks removed from the playlist.",
    )
    unchanged: int = Field(
        description="The number of tracks that were in the playlist before and after the sync.",
    )
    difference: int = Field(
        description="The difference between the total number tracks in the playlist from before and after the sync.",
    )
    final: int = Field(
        description="The total number of tracks in the playlist after the sync.",
    )

    @classmethod
    def from_paths(cls, initial: Sequence[Path], final: Sequence[Path]) -> Self:
        initial_counts = Counter(initial)
        final_counts = Counter(final)

        added = sum((final_counts - initial_counts).values())
        removed = sum((initial_counts - final_counts).values())
        intersection = initial_counts & final_counts

        return cls(
            start=len(initial),
            added=added,
            removed=removed,
            unchanged=sum(intersection.values()),
            difference=added - removed,
            final=len(final),
        )


@final_decorator
class M3U(LocalPlaylist[PathsFilter]):
    """For reading and writing data from M3U playlist format."""
    __supported_extensions__ = frozenset({"m3u"})
    __final__ = True
    
    @staticmethod
    async def _load_track(path: str | Path) -> LocalTrack:
        file = await LocalTrack.load_file(path)
        return TypeAdapter(LocalTrack.annotation).validate_python(file)

    async def load(self, tracks: Collection[LocalTrack] = ()) -> Self:
        """
        Read the playlist file and update the tracks in this playlist instance.

        :param tracks: Available Tracks to search through for matches.
            If no tracks are given, the playlist instance will load all the tracks
            from scratch according to its settings.
        :return: Self
        """
        paths: list[str] = []
        if self.path.is_file():  # load from file
            with open(self.path, "r", encoding="utf-8") as file:
                paths = [line.strip() for line in file]

            if not paths:  # clear on empty playlist file
                self.tracks.clear()
                self._original.clear()
                return self

        self.matcher = PathsFilter(values=set(paths), path_mapper=self.path_mapper)
        paths = self.path_mapper.map_many(paths, check_existence=not bool(tracks))

        if tracks:  # match paths from given tracks using the matcher
            self._match_tracks(tracks)
        else:  # use the paths in the matcher to load tracks from scratch
            # TODO: support m3u playlists with duplicate paths?
            self.tracks[:] = await asyncio.gather(*map(self._load_track, set(paths)))

        self._limit_tracks(ignore=paths)
        self._sort_tracks(paths=list(map(Path, paths)))

        self._original = self.tracks.copy() if self.path.is_file() else []

        return self

    def _sort_tracks(self, paths: Sequence[Path] = ()) -> None:
        if self.sorter is not None or not paths:
            return super()._sort_tracks()

        self.tracks.sort(key=lambda track: paths.index(track.path))

    async def save(self, dry_run: bool = True, *_, **__) -> SyncResultM3U:
        """
        Write the tracks in this Playlist and its settings (if applicable) to file.

        :param dry_run: Run function, but do not modify the file on the disk.
        :return: The results of the sync as a :py:class:`SyncResultM3U` object.
        """
        start_paths = list(map(Path, self.path_mapper.unmap_many(self._original, check_existence=False)))

        if not dry_run:
            await self.rename()

            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("w", encoding="utf-8") as file:
                # reassign any original folder found by the matcher and output
                paths = self.path_mapper.unmap_many(self.tracks, check_existence=False)
                file.writelines(path.strip() + '\n' for path in paths)

            self._original = self.tracks.copy()  # update original tracks to newly saved tracks

        final_paths = list(map(Path, self.path_mapper.unmap_many(self.tracks, check_existence=False)))
        return SyncResultM3U.from_paths(start_paths, final_paths)
