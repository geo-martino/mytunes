from abc import abstractmethod
from collections.abc import Collection, MutableMapping, MutableSequence, Sequence
from pathlib import Path
from typing import Any, Annotated

import mutagen
from pydantic import Field, model_validator, PrivateAttr

from musify.local._collection._base import LocalCollection
from musify.local._collection.playlist.result import LimitResult, SortResult, LoadPlaylistResult, SavePlaylistResult
from musify.processors.filters import Filter
from musify.processors.filters.composite import CompositeFilter, CompositeResult, \
    IncludeExcludeResult
from musify.processors.limit import ItemLimiter
from musify.processors.sort import ItemSorter
from ..._item.track import LocalTrack, HasLocalTracks
from ...._models import makecls
from ...._models.collection.playlist import MutablePlaylist
from ...._models.metadata import UniqueAttribute
from ...._models.properties.file import IsLocalFile, IsReadableFile, IsWriteableFile, PathMapper
from ...._models.properties.uri import URI
from ...._models.sequence import MutableUniqueSequence, UniqueSequence


class LocalPlaylistFile[TF: Filter](
    IsLocalFile,
    LocalCollection[LocalTrack],
    MutablePlaylist[URI, LocalTrack[mutagen.FileType]],
    HasLocalTracks[URI, LocalTrack[mutagen.FileType]],
    metaclass=makecls()
):
    _original: MutableUniqueSequence[str, LocalTrack] = PrivateAttr(default_factory=MutableUniqueSequence)

    # override to apply uniqueness metadata
    path: Annotated[Path, UniqueAttribute()] = Field(
        description="The path to the playlist file on the local filesystem."
    )
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

    @model_validator(mode="before")
    @classmethod
    def _extract_name_from_path[T](cls, data: T | MutableMapping[str, Any]) -> T | MutableMapping[str, Any]:
        if not isinstance(data, MutableMapping) or "name" in data or (path := data.get("path")) is None:
            return data

        path = Path(path)
        data["name"] = path.stem
        return data

    @model_validator(mode="before")
    @classmethod
    def _from_path[T](cls, data: T | str | Path) -> T | dict[str, Any]:
        if not isinstance(data, str | Path):
            return data
        return dict(path=Path(data))

    def _match_tracks(
            self, tracks: Collection[LocalTrack] = (), reference: LocalTrack | None = None
    ) -> CompositeResult[LocalTrack]:
        match self.matcher:
            case None:
                return IncludeExcludeResult(included=tuple(tracks))
            case CompositeFilter():
                return self.matcher.match(tracks, reference=reference)
            case _:
                include = self.matcher.apply(tracks, reference=reference)
                return IncludeExcludeResult(included=tuple(include))

    def _limit_tracks(
            self, tracks: Sequence[LocalTrack], ignore: Collection[str | Path | LocalTrack]
    ) -> LimitResult:
        if self.limiter is None or not tracks:
            return LimitResult(limited=tuple(tracks))

        tracks_unique = UniqueSequence(tracks)
        ignore = [i if isinstance(i, LocalTrack) else tracks_unique.get(i) for i in ignore]
        ignore = tuple(filter(None, ignore))

        if not isinstance(tracks, MutableSequence):
            tracks = list(tracks)
        self.limiter.limit(tracks, ignore=ignore)

        return LimitResult(limited=tuple(tracks), limit_ignored=tuple(ignore))

    def _sort_tracks(self, tracks: Sequence[LocalTrack]) -> SortResult:
        if self.sorter is None or not tracks:
            return SortResult(sorted=tuple(tracks))

        if not isinstance(tracks, MutableSequence):
            tracks = list(tracks)
        self.sorter.sort(tracks)

        return SortResult(sorted=tuple(tracks))

    async def rename(self) -> None:
        """Rename the playlist file to match the name of the playlist."""
        if self.name == self.path.stem:
            return

        path = self.path.with_stem(self.name)
        self.path = self.path.rename(path)


# noinspection PyAbstractClass
class LocalPlaylist[TF: Filter](LocalPlaylistFile[TF], IsReadableFile, IsWriteableFile):
    @abstractmethod
    async def load(self, tracks: Collection[LocalTrack] = ()) -> LoadPlaylistResult:
        """
        Read the playlist file and update the tracks in this playlist instance.

        :param tracks: Available Tracks to search through for matches.
        :return: Self
        """
        raise NotImplementedError

    @abstractmethod
    async def save(self, dry_run: bool = True, *args, **kwargs) -> SavePlaylistResult:
        """
        Write the tracks in this Playlist and its settings (if applicable) to file.

        :param dry_run: Run function, but do not modify the file on the disk.
        :return: :py:class:`Result` object with stats on the changes to the playlist.
        """
        raise NotImplementedError
