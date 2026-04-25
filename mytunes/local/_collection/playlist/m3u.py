from collections import Counter
from collections.abc import Sequence, Collection
from pathlib import Path
from typing import Self, final as final_decorator, Annotated

import aiofiles
from pydantic import Field, NonNegativeInt, validate_call

from mytunes.core.properties.path import PathInputType
from mytunes.core.sequence import MutableUniqueSequence
from mytunes.local._collection.playlist import LocalPlaylist
from mytunes.local._collection.playlist.result import SortResult, LoadPlaylistResult, SavePlaylistResult
from mytunes.processors.filters.values import PathFilter
from mytunes.result import LogFormatter
from ..._item.track import LocalTrack, LOCAL_TRACK_ADAPTER


class SyncM3UResult(SavePlaylistResult):
    """Stores the results of a sync with a local M3U playlist"""
    start: Annotated[
        NonNegativeInt,
        LogFormatter(width=6, alignment="right", colour="blue", colour_attributes=["bold"]),
    ] = Field(
        description="The total number of tracks in the playlist before the sync."
    )
    added: Annotated[
        NonNegativeInt,
        LogFormatter(
            width=6, alignment="right", colour="blue", colour_attributes=["bold"], condition=lambda x: x == 0
        ),
        LogFormatter(
            width=6, alignment="right", colour="green", colour_attributes=["bold"], condition=lambda x: x > 0
        ),
    ] = Field(
        description="The number of tracks added to the playlist."
    )
    removed: Annotated[
        NonNegativeInt,
        LogFormatter(
            width=6, alignment="right", colour="blue", colour_attributes=["bold"], condition=lambda x: x == 0
        ),
        LogFormatter(
            width=6, alignment="right", colour="red", colour_attributes=["bold"], condition=lambda x: x > 0
        ),
    ] = Field(
        description="The number of tracks removed from the playlist."
    )
    unchanged: Annotated[
        NonNegativeInt,
        LogFormatter(
            width=6, alignment="right", colour="blue", colour_attributes=["bold"], condition=lambda x: x == 0
        ),
        LogFormatter(
            width=6, alignment="right", colour="yellow", colour_attributes=["bold"], condition=lambda x: x > 0
        ),
    ] = Field(
        description="The number of tracks that were in the playlist both before and after the sync."
    )
    difference: Annotated[
        int,
        LogFormatter(
            width=6, alignment="right", colour="blue", colour_attributes=["bold"], condition=lambda x: x == 0),
        LogFormatter(
            width=6, alignment="right", colour="magenta", colour_attributes=["bold"], condition=lambda x: x != 0),
    ] = Field(
        description="The difference between the total number tracks from before and after the sync."
    )
    final: Annotated[
        NonNegativeInt,
        LogFormatter(width=6, alignment="right", colour="blue", colour_attributes=["bold"]),
    ] = Field(
        description="The total number of tracks in the playlist after the sync."
    )

    @classmethod
    def from_paths(cls, name: str, initial: Sequence[Path], final: Sequence[Path]) -> Self:
        initial_counts = Counter(initial)
        final_counts = Counter(final)

        added = sum((final_counts - initial_counts).values())
        removed = sum((initial_counts - final_counts).values())
        intersection = initial_counts & final_counts

        return cls(
            name=name,
            start=len(initial),
            added=added,
            removed=removed,
            unchanged=sum(intersection.values()),
            difference=added - removed,
            final=len(final),
        )


@final_decorator
class M3U(LocalPlaylist[PathFilter]):
    """For reading and writing data from M3U playlist format."""
    __final__ = True
    __supported_extensions__ = frozenset({"m3u"})

    @staticmethod
    async def _load_track(path: str | Path) -> LocalTrack:
        file = await LocalTrack.load_file(path)
        return LOCAL_TRACK_ADAPTER.validate_python(file)

    async def load(self, tracks: Collection[LocalTrack] = ()) -> LoadPlaylistResult:
        """
        Read the playlist file and update the tracks in this playlist instance.

        :param tracks: Available Tracks to search through for matches.
            If no tracks are given, the playlist instance will load all the tracks
            from scratch according to its settings.
        :return: Self
        """
        # TODO: support m3u playlists with duplicate paths?
        if not self.path.is_file():  # just use the given tracks against the current settings
            return self._load_from_tracks(tracks)

        with open(self.path, "r", encoding="utf-8") as file:
            paths = [line.strip() for line in file]

        if not paths:  # clear on empty playlist file
            self.tracks.clear()
            self._original.clear()
            return LoadPlaylistResult(name=self.name)

        self.matcher: PathFilter = PathFilter(values=set(paths), path_mapper=self.path_mapper)

        if not tracks:  # load the tracks from the paths in file
            task_id = self._progress.add_task(
                description=f"Loading {type(self).__name__} tracks", visible=False
            )
            tasks = map(self._load_track, self.matcher.paths_valid)
            tracks = await self._run_tasks_async(tasks, task_id=task_id)
            tracks = MutableUniqueSequence(tracks)

        result = self._load_from_tracks(tracks, paths=paths)
        self._original = self.tracks.copy()

        return result

    def _load_from_tracks(
            self, tracks: Collection[LocalTrack], paths: Sequence[PathInputType] = ()
    ) -> LoadPlaylistResult:
        paths = self.path_mapper.serialise_many_to_paths(paths, check_existence=False)

        match_result = self._match_tracks(tracks)
        limit_result = self._limit_tracks(tracks=match_result.combined, ignore=paths)
        sort_result = self._sort_tracks(tracks=limit_result.limited, paths=paths)

        result = LoadPlaylistResult.from_results(
            name=self.name, match=match_result, limit=limit_result, sort=sort_result
        )
        self.tracks.replace(result.tracks)

        return result

    def _sort_tracks(self, tracks: Sequence[LocalTrack], paths: Sequence[Path] = ()) -> SortResult:
        if self.sorter is not None or not paths:
            return super()._sort_tracks(tracks)

        tracks = sorted(tracks, key=lambda track: paths.index(track.path))
        return SortResult(sorted=tuple(tracks))

    async def save(self, dry_run: bool = False) -> SyncM3UResult:
        """
        Write the tracks in this Playlist and its settings (if applicable) to file.

        :param dry_run: Run function, but do not modify the file on the disk.
        :return: The results of the sync.
        """
        start_paths = list(map(Path, self.path_mapper.deserialise_many(self._original, check_existence=False)))

        if not dry_run:
            self.path.parent.mkdir(parents=True, exist_ok=True)

            self.filename = self.name  # renames the file if it exists
            async with aiofiles.open(self.path, "w", encoding="utf-8") as file:
                # reassign any original folder found by the matcher and output
                paths = self.path_mapper.deserialise_many(self.tracks, check_existence=False)
                await file.writelines(path.strip() + "\n" for path in paths)

            self._original = self.tracks.copy()  # update original tracks to newly library tracks

        final_paths = list(map(Path, self.path_mapper.deserialise_many(self.tracks, check_existence=False)))
        return SyncM3UResult.from_paths(self.name, initial=start_paths, final=final_paths)
