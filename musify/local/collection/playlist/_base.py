from abc import abstractmethod
from collections.abc import Collection, MutableMapping
from pathlib import Path
from typing import Self, Any

from pydantic import Field, model_validator, PrivateAttr, ModelWrapValidatorHandler

from musify.local.collection._base import LocalCollection
from musify.local.item.track import LocalTrack
from musify.models.collection.playlist import MutablePlaylist
from musify.models.properties.file import IsLocalFile, IsReadableFile, IsWriteableFile, PathMapper
from musify.models.properties.logger import HasLogger
from musify.models.properties.uri import URI
from musify.models.sequence import MusifyMutableSequence
from musify.processors_new import Result
from musify.processors_new.filters import Filter, MatchFilter
from musify.processors_new.limit import ItemLimiter
from musify.processors_new.sort import ItemSorter


class LocalPlaylistFile[TF: Filter](
    LocalCollection, MutablePlaylist[str, LocalTrack, URI], IsLocalFile, HasLogger
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
    @model_validator(mode="wrap")
    @classmethod
    def _extract_name_from_path(
            cls, data: str | Path | MutableMapping[str, Any], handler: ModelWrapValidatorHandler[Self]
    ) -> Self:
        if isinstance(data, str | Path):
            data = dict(path=Path(data))
        if not isinstance(data, MutableMapping) or "name" in data or (path := data.get("path")) is None:
            return handler(data)

        path = Path(path)
        data["name"] = path.stem
        return handler(data)

    def _match_tracks(self, tracks: Collection[LocalTrack] = (), reference: LocalTrack | None = None) -> None:
        match self.matcher:
            case None:
                return
            case MatchFilter():
                result = self.matcher.match(tracks, reference=reference)
                lengths = ' '.join(f"{k}={v}" for k, v in result.lengths.items())
                tracks = result.combined
                self.logger.debug(f"{self.name!r} matched: {lengths} combined={len(tracks)}")
            case _:
                tracks = self.matcher.apply(tracks, reference=reference)
                self.logger.debug(f"{self.name!r} matched: {len(tracks)}")

        self.tracks[:] = tracks

    def _limit_tracks(self, ignore: Collection[str | Path | LocalTrack]) -> None:
        if self.limiter is None or not self.tracks:
            return

        start = len(self.tracks)
        ignore = [i if isinstance(i, LocalTrack) else self.tracks.get(str(i)) for i in ignore]
        self.limiter.limit(self.tracks, ignore=[i for i in ignore if i is not None])

        self.logger.debug(f"{self.name!r} limited: start={start} final={len(self.tracks)} ignored={len(ignore)}")

    def _sort_tracks(self) -> None:
        if self.sorter is None or not self.tracks:
            return

        self.sorter.sort(self.tracks)
        self.logger.debug(f"{self.name!r} sorted: {len(self.tracks)}")

    async def rename(self) -> None:
        """Rename the playlist file to match the name of the playlist."""
        if self.name == self.path.stem:
            return

        path = self.path.with_stem(self.name)
        self.path = self.path.rename(path)


# noinspection PyAbstractClass
class LocalPlaylist[TF: Filter](LocalPlaylistFile[TF], IsReadableFile, IsWriteableFile):
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
