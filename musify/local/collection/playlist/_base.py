from abc import ABCMeta, abstractmethod
from collections.abc import Collection
from pathlib import Path, PurePath
from typing import Self, Any

from pydantic import Field, model_validator, PrivateAttr

from musify.local.collection._base import LocalCollection
from musify.local.item.track import LocalTrack
from musify.models.collection.playlist import Playlist
from musify.models.item.track import HasMutableTracks
from musify.models.properties.file import _IsFile, IsFile, PathMapper
from musify.models.sequence import MusifyMutableSequence
from musify.processors_new import Result
from musify.processors_new.filters import Filter
from musify.processors_new.limit import ItemLimiter
from musify.processors_new.sort import ItemSorter


class _LocalPlaylist[TF: Filter](
    LocalCollection, HasMutableTracks[str, LocalTrack], Playlist[str, LocalTrack], _IsFile
):
    __unique_attributes__ = frozenset({"path"})

    _original: MusifyMutableSequence[str, LocalTrack] = PrivateAttr(default_factory=MusifyMutableSequence)

    matcher: TF | None = Field(
        description="Filter object to use for matching tracks.",
        default=None,
    )
    limiter: ItemLimiter | None = Field(
        description="ItemLimiter object to use for limiting the number of tracks matched.",
        default=None,
    )
    sorter: ItemSorter | None = Field(
        description="ItemSorter object to use when sorting the final track list.",
        default=None,
    )
    path_mapper: PathMapper = Field(
        description="Mapper to use when mapping paths stored in the playlist file.",
        default_factory=PathMapper,
    )

    # noinspection PyNestedDecorators
    @model_validator(mode="before")
    @classmethod
    def _extract_name_from_path[T](cls, value: T) -> T | dict[str, Any]:
        value = cls._map_path(value)
        if not isinstance(value, dict) or "name" in value or (path := value.get("path")) is None:
            return value
        return value | {"name": PurePath(str(path)).stem}

    def _match_tracks(self, tracks: Collection[LocalTrack] = (), reference: LocalTrack | None = None) -> None:
        if self.matcher is None:
            return
        self.tracks[:] = self.matcher.apply(tracks, reference=reference)

    def _limit_tracks(self, ignore: Collection[str | Path | LocalTrack]) -> None:
        if self.limiter is None or not self.tracks:
            return
        ignore = [i if isinstance(i, LocalTrack) else self.tracks.get(str(i)) for i in ignore]
        self.limiter.limit(self.tracks, ignore=[i for i in ignore if i is not None])

    def _sort_tracks(self) -> None:
        if self.sorter is None or not self.tracks:
            return
        self.sorter.sort(self.tracks)

    async def rename(self) -> None:
        """Rename the playlist file to match the name of the playlist."""
        if self.name == self.path.stem:
            return

        path = self.path.with_stem(self.name)
        self.path = self.path.rename(path)


class LocalPlaylist[TF: Filter](_LocalPlaylist[TF], IsFile, metaclass=ABCMeta):
    @abstractmethod
    async def load(self, tracks: Collection[LocalTrack] = ()) -> Self:
        """
        Read the playlist file and update the tracks in this playlist instance.

        :param tracks: Available Tracks to search through for matches.
        :return: Self
        """
        raise NotImplementedError

    @abstractmethod
    async def save(self, dry_run: bool = True, *args, **kwargs) -> Result:
        """
        Write the tracks in this Playlist and its settings (if applicable) to file.

        :param dry_run: Run function, but do not modify the file on the disk.
        :return: :py:class:`Result` object with stats on the changes to the playlist.
        """
        raise NotImplementedError
