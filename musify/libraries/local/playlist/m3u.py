"""
The M3U implementation of a :py:class:`LocalPlaylist`.
"""
import asyncio
from collections.abc import Collection
from dataclasses import dataclass
from pathlib import Path
from typing import Self

from musify.base import Result
from musify.file.base import File
from musify.file.path_mapper import PathMapper
from musify.libraries.local.playlist.base import LocalPlaylist
from musify.libraries.local.track import LocalTrack, load_track
from musify.libraries.remote.core.wrangle import RemoteDataWrangler
from musify.processors.filter import FilterDefinedList


@dataclass(frozen=True)
class SyncResultM3U(Result):
    """Stores the results of a sync with a local M3U playlist"""
    #: The total number of tracks in the playlist before the sync.
    start: int
    #: The number of tracks added to the playlist.
    added: int
    #: The number of tracks removed from the playlist.
    removed: int
    #: The number of tracks that were in the playlist before and after the sync.
    unchanged: int
    #: The difference between the total number tracks in the playlist from before and after the sync.
    difference: int
    #: The total number of tracks in the playlist after the sync.
    final: int


class M3U(LocalPlaylist[FilterDefinedList[str | Path | File]]):
    """
    For reading and writing data from M3U playlist format.

    :param path: Absolute path of the playlist.
        If the playlist ``path`` given does not exist, a new playlist will be created on :py:meth:`save`
    :param path_mapper: Optionally, provide a :py:class:`PathMapper` for paths stored in the playlist file.
        Useful if the playlist file contains relative paths and/or paths for other systems that need to be
        mapped to absolute, system-specific paths to be loaded and back again when saved.
    :param remote_wrangler: Optionally, provide a :py:class:`RemoteDataWrangler` object for processing URIs on tracks.
        If given, the wrangler can be used when calling __get_item__ to get an item from the collection from its URI.
        The wrangler is also used when loading tracks to allow them to process URI tags.
        For more info on this, see :py:class:`LocalTrack`.
    """

    __slots__ = ("_description",)

    valid_extensions = frozenset({".m3u"})

    @property
    def description(self):
        return self._description

    @description.setter
    def description(self, value: str | None):
        self._description = value

    @property
    def image_links(self):
        return {}

    def __init__(
            self,
            path: str | Path,
            path_mapper: PathMapper = PathMapper(),
            remote_wrangler: RemoteDataWrangler = None,
    ):
        super().__init__(path=path, path_mapper=path_mapper, remote_wrangler=remote_wrangler)

        self._description = None

    async def _load_track(self, path: str | Path) -> LocalTrack:
        path = self.path_mapper.map(path, check_existence=True)
        return await load_track(path=path, remote_wrangler=self.remote_wrangler)

    async def load(self, tracks: Collection[LocalTrack] = ()) -> Self:
        """
        Read the playlist file and update the tracks in this playlist instance.

        :param tracks: Available Tracks to search through for matches.
            If no tracks are given, the playlist instance will load all the tracks
            from scratch according to its settings.
        :return: Self
        """
        path_list: list[Path] = []
        if self.path.is_file():  # load from file
            with open(self.path, "r", encoding="utf-8") as file:
                paths_raw = self.path_mapper.map_many([line.strip() for line in file], check_existence=True)
            path_list = list(map(Path, paths_raw))

            if not path_list:  # empty playlist file
                self.clear()
                self._original = []
                return self

        self.matcher = FilterDefinedList(values=path_list)
        self.matcher.transform = lambda x: Path(self.path_mapper.map(x, check_existence=False))

        if tracks:  # match paths from given tracks using the matcher
            self._match(tracks)
        else:  # use the paths in the matcher to load tracks from scratch
            self.tracks = await asyncio.gather(
                *map(self._load_track, filter(lambda path: path is not None, self.matcher.values))
            )

        self._limit(ignore=self.matcher.values)
        self._sort()

        self._original = self.tracks.copy() if self._path.is_file() else []

        return self

    async def save(self, dry_run: bool = True, *_, **__) -> SyncResultM3U:
        """
        Write the tracks in this Playlist and its settings (if applicable) to file.

        :param dry_run: Run function, but do not modify the file on the disk.
        :return: The results of the sync as a :py:class:`SyncResultM3U` object.
        """
        start_paths = set(map(Path, self.path_mapper.unmap_many(self._original, check_existence=False)))
        self.path.parent.mkdir(parents=True, exist_ok=True)

        if not dry_run:
            with open(self.path, "w", encoding="utf-8") as file:
                # reassign any original folder found by the matcher and output
                paths = self.path_mapper.unmap_many(self.tracks, check_existence=False)
                file.writelines(path.strip() + '\n' for path in paths)

            self._original = self.tracks.copy()  # update original tracks to newly saved tracks

            with open(self.path, "r", encoding="utf-8") as file:  # get list of paths that were saved for results
                final_paths = {Path(line.rstrip()) for line in file if line.rstrip()}
        else:  # use current list of tracks as a proxy of paths that were saved for results
            final_paths = set(map(Path, self.path_mapper.unmap_many(self._tracks, check_existence=False)))

        return SyncResultM3U(
            start=len(start_paths),
            added=len(final_paths - start_paths),
            removed=len(start_paths.difference(final_paths)),
            unchanged=len(start_paths.intersection(final_paths)),
            difference=len(final_paths) - len(start_paths),
            final=len(final_paths),
        )
