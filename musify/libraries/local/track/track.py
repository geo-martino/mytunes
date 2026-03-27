"""
Compositely combine reader and writer classes for metadata/tags/properties operations on Track files.
"""
import datetime
import re
from abc import ABCMeta, abstractmethod
from collections.abc import Generator
from copy import deepcopy, copy
from pathlib import Path
from typing import Any, Self

import mutagen
from aiorequestful.types import UnitIterable
from yarl import URL

from musify.base import MusifyItem
from musify.exception import MusifyKeyError, MusifyAttributeError, MusifyTypeError, MusifyValueError
from musify.field import TagMap
from musify.field import TrackField
from musify.file.exception import FileDoesNotExistError, UnexpectedPathError
from musify.libraries.core.object import Track
from musify.libraries.local.base import LocalItem
# noinspection PyProtectedMember
from musify.libraries.local.track._tags import TagReader, TagWriter, SyncResultTrack
from musify.libraries.local.track.field import LocalTrackField as Tags, LocalTrackField
from musify.libraries.remote.core.wrangle import RemoteDataWrangler
from musify.utils import to_collection


class LocalTrack[T: mutagen.FileType, U: TagReader, V: TagWriter](LocalItem, Track, metaclass=ABCMeta):
    """
    Generic track object for extracting, modifying, and saving metadata/tags/properties for a given file.

    :param file: The path or Mutagen object of the file to load.
    :param remote_wrangler: Optionally, provide a :py:class:`RemoteDataWrangler` object for processing URIs.
        This object will be used to check for and validate a URI tag on the file.
        The tag that is used for reading and writing is set by the ``uri_tag`` class attribute.
        If no ``remote_wrangler`` is given, no URI processing will occur.
    """

    __slots__ = (
        "_path",
        "_new_path",
        "_remote_wrangler",
        "_reader",
        "_writer",
        "_loaded",
        "_title",
        "_artist",
        "_album",
        "_album_artist",
        "_track_number",
        "_track_total",
        "_genres",
        "_year",
        "_month",
        "_day",
        "_bpm",
        "_key",
        "_disc_number",
        "_disc_total",
        "_compilation",
        "_comments",
        "_uri",
        "_has_uri",
        "_image_links",
        "_has_image",
        "_rating",
        "_date_added",
        "_last_played",
        "_play_count",
    )
    __attributes_classes__ = (Track, LocalItem)
    __attributes_ignore__ = ("tag_map",)

    @property
    def name(self):
        return self.title or self.filename

    @property
    @abstractmethod
    def tag_map(self) -> TagMap:
        """The map of tag names to tag IDs for the given file type."""
        raise NotImplementedError

    @property
    def title(self):
        return self._title

    @title.setter
    def title(self, value: str | None):
        self._title = value

    @property
    def artist(self):
        return self._artist

    @artist.setter
    def artist(self, value: str | None):
        self._artist = value

    @property
    def artists(self) -> list[str]:
        return self._artist.split(self.tag_sep) if self._artist else []

    @artists.setter
    def artists(self, value: list[str | None]):
        if value:
            value = self.tag_sep.join(value)
        self._artist = value

    @property
    def album(self):
        return self._album

    @album.setter
    def album(self, value: str | None):
        self._album = value

    @property
    def album_artist(self):
        return self._album_artist

    @album_artist.setter
    def album_artist(self, value: str | None):
        self._album_artist = value

    @property
    def track_number(self):
        return self._track_number

    @track_number.setter
    def track_number(self, value: int | None):
        self._track_number = value

    @property
    def track_total(self):
        return self._track_total

    @track_total.setter
    def track_total(self, value: int | None):
        self._track_total = value

    @property
    def genres(self):
        return self._genres

    @genres.setter
    def genres(self, value: list[str] | None):
        self._genres = value

    @property
    def date(self):
        if self._year and self._month and self._day:
            return datetime.date(self._year, self._month, self._day)

    @date.setter
    def date(self, value: str | datetime.date | None):
        if isinstance(value, str):
            value = datetime.datetime.strptime(value, "%Y-%m-%d")
        self._year = value.year if value else None
        self._month = value.month if value else None
        self._day = value.day if value else None

    @property
    def year(self):
        return self._year

    @year.setter
    def year(self, value: int | None):
        if value and value < 1000:
            raise MusifyValueError(f"Year value is invalid: {value}")
        self._year = value

    @property
    def month(self):
        return self._month

    @month.setter
    def month(self, value: int | None):
        if value and (value < 1 or value > 12):
            raise MusifyValueError(f"Month value is invalid: {value}")
        self._month = value

    @property
    def day(self):
        return self._day

    @day.setter
    def day(self, value: int | None):
        if value and (value < 1 or value > 31):
            raise MusifyValueError(f"Day value is invalid: {value}")
        self._day = value

    @property
    def bpm(self):
        return self._bpm

    @bpm.setter
    def bpm(self, value: float | None):
        self._bpm = value

    @property
    def key(self):
        return self._key

    @key.setter
    def key(self, value: str | None):
        self._key = value

    @property
    def disc_number(self):
        return self._disc_number

    @disc_number.setter
    def disc_number(self, value: int | None):
        self._disc_number = value

    @property
    def disc_total(self):
        return self._disc_total

    @disc_total.setter
    def disc_total(self, value: int | None):
        self._disc_total = value

    @property
    def compilation(self):
        return self._compilation

    @compilation.setter
    def compilation(self, value: bool | None):
        self._compilation = value

    @property
    def comments(self):
        return self._comments

    @comments.setter
    def comments(self, value: UnitIterable[str] | None):
        self._comments = [value] if isinstance(value, str) else to_collection(value, list)

    def _uri_getter(self):
        return self._uri

    def _uri_setter(self, value: str | None):
        if value is None:
            self._uri = None
            self._has_uri = None
        elif self._reader.unavailable_uri_dummy is not None and value == self._reader.unavailable_uri_dummy:
            self._uri = None
            self._has_uri = False
        else:
            self._uri = value
            self._has_uri = True

        if self._loaded:
            setattr(self, self._reader.uri_tag.name.lower(), value)

    @property
    def has_uri(self):
        return self._has_uri

    @property
    def image_links(self):
        return self._image_links

    @image_links.setter
    def image_links(self, value: dict[str, str | Path | URL]):
        self._image_links = value

    @property
    def has_image(self):
        return self._has_image

    @has_image.setter
    def has_image(self, value: bool):
        self._has_image = value

    @property
    def length(self):
        return self._reader.file.info.length

    @property
    def rating(self):
        return self._rating

    @rating.setter
    def rating(self, value: float | None):
        self._rating = value

    @property
    def path(self):
        return self._path

    @path.setter
    def path(self, value: str | Path):
        if isinstance(value, str):
            value = Path(re.sub(r"[<>:\"|?*]", "-", value))
        self._new_path = Path(value)

    @property
    def filename(self):
        """The filename without extension."""
        return super().filename

    @filename.setter
    def filename(self, value: str | Path):
        if isinstance(value, Path):
            value = value.stem
        value = re.sub(r"[/\\]", "-", str(value))
        self.path = str(self.path.with_stem(value))

    @property
    def type(self):
        """The type of audio file of this track"""
        return self.__class__.__name__

    @property
    def channels(self) -> int:
        """The number of channels in this audio file i.e. 1 for mono, 2 for stereo, ..."""
        return self._reader.file.info.channels

    @property
    def bit_rate(self) -> float:
        """The bit rate of this track in kilobytes per second"""
        return self._reader.file.info.bitrate / 1000

    @property
    def bit_depth(self) -> int | None:
        """The bit depth of this track in bits"""
        try:
            return self._reader.file.info.bits_per_sample
        except AttributeError:
            return None

    @property
    def sample_rate(self) -> float:
        """The sample rate of this track in kHz"""
        return self._reader.file.info.sample_rate / 1000

    @property
    def date_added(self) -> datetime.datetime | None:
        """The timestamp for when this track was added to the associated collection"""
        return self._date_added

    @date_added.setter
    def date_added(self, value: datetime.datetime | None):
        self._date_added = value

    @property
    def last_played(self) -> datetime.datetime | None:
        """The timestamp when this track was last played"""
        return self._last_played

    @last_played.setter
    def last_played(self, value: datetime.datetime | None):
        self._last_played = value

    @property
    def play_count(self) -> int | None:
        """The total number of times this track has been played"""
        return self._play_count

    @play_count.setter
    def play_count(self, value: int | None):
        self._play_count = value

    @abstractmethod
    def _create_reader(self, file: T) -> U:
        """Return a :py:class:`TagReader` object for this track type"""
        raise NotImplementedError

    @abstractmethod
    def _create_writer(self, file: T) -> V:
        """Return a :py:class:`TagWriter` object for this track type"""
        raise NotImplementedError

    def __init__(self, file: str | Path | T, remote_wrangler: RemoteDataWrangler = None):
        super().__init__()

        self._path: Path = Path(file if isinstance(file, str | Path) else file.filename)
        self._new_path = self._path
        self._validate_type(self._path)

        self._remote_wrangler = remote_wrangler

        self._loaded = False
        self._reader: TagReader[T] | None = None
        self._writer: TagWriter[T] | None = None

        self._title = None
        self._artist = None
        self._album = None
        self._album_artist = None
        self._track_number = None
        self._track_total = None
        self._genres = None
        self._year = None
        self._month = None
        self._day = None
        self._bpm = None
        self._key = None
        self._disc_number = None
        self._disc_total = None
        self._compilation = None
        self._comments = None

        self._uri = None
        self._has_uri = None
        self._has_image = None
        self._image_links = {}

        self._rating = None
        self._date_added = None
        self._last_played = None
        self._play_count = None

        if isinstance(file, mutagen.FileType):
            self._reader = self._create_reader(file)
            self._writer = self._create_writer(file)
            self.refresh()

    def __await__(self) -> Generator[Any, None, Self]:
        return self.load().__await__()

    async def load(self) -> Self:
        """
        Load local file from scratch using mutagen from the path stored in this object.
        Refreshes the metadata loaded into this object and returns self.

        :return: Self.
        :raise FileDoesNotExistError: If the file cannot be found.
        :raise InvalidFileType: If the file type is not supported.
        """
        if not self._path.is_file():
            raise FileDoesNotExistError(self._path)

        file = mutagen.File(self.path)
        self._reader = self._create_reader(file)
        self._writer = self._create_writer(file)

        self.refresh()

        return self

    def refresh(self) -> None:
        """Extract update tags for this object from the loaded mutagen object."""
        self._refresh()

        # to reduce memory usage, remove any embedded images from the loaded file
        self._writer.clear_loaded_images()

        self._loaded = True

    def _refresh(self):
        """Simply refresh the metadata from file without any post-processing."""
        self.title = self._reader.read_title()
        self.artist = self._reader.read_artist()
        self.album = self._reader.read_album()
        self.album_artist = self._reader.read_album_artist()
        self.track_number = self._reader.read_track_number()
        self.track_total = self._reader.read_track_total()
        self.genres = self._reader.read_genres()
        self.year, self.month, self.day = self._reader.read_date() or (None, None, None)
        self.bpm = self._reader.read_bpm()
        self.key = self._reader.read_key()
        self.disc_number = self._reader.read_disc_number()
        self.disc_total = self._reader.read_disc_total()
        self.compilation = self._reader.read_compilation()
        self.comments = self._reader.read_comments()

        self.uri = self._reader.read_uri()
        if not self._loaded:
            self.has_image = self._reader.check_for_images()

    async def save(
            self, tags: UnitIterable[Tags] = Tags.ALL, replace: bool = False, dry_run: bool = True
    ) -> SyncResultTrack:
        """
        Update file's tags from given dictionary of tags.

        :param tags: Tags to be updated.
        :param replace: Destructively replace tags in each file.
        :param dry_run: Run function, but do not modify the file on the disk.
        :return: List of tags that have been updated.
        """
        # copy and reload the mutagen object to ensure comparison are being made against current data
        current = copy(self)
        current._writer.file.load(current._writer.file.filename)
        current._refresh()

        result = self._writer.write(source=current, target=self, tags=tags, replace=replace, dry_run=dry_run)

        path_fields = (Tags.PATH, Tags.FOLDER, Tags.FILENAME)
        if tags == LocalTrackField.ALL or any((field in to_collection(tags) for field in path_fields)):
            if self._new_path != self.path:
                if not dry_run:
                    await self.move(self._new_path)
                result = SyncResultTrack(saved=result.saved or not dry_run, updated=result.updated | {Tags.PATH: 0})

        # to reduce memory usage, remove any embedded images from the loaded file
        current._writer.clear_loaded_images()
        return result

    async def move(self, path: str | Path) -> None:
        """
        Move the file on the drive.

        Updates the path properties of this object to represent the new file path.
        Creates parent directories at the new location if necessary.

        :param path: The path to move the file to.
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        self._path = self.path.rename(path)
        self._reader.file.filename = str(self.path)
        self._writer.file.filename = str(self.path)

    async def rename(self, filename: str | Path) -> None:
        """
        Rename the file on the drive.

        Updates the path properties of this object to represent the new file path.
        Creates parent directories at the new location if necessary.

        :param filename: The filename to move the file to.
            Argument may be a path from which the filename will be extracted.
        """
        if isinstance(filename, Path):
            filename = filename.stem

        path = self.path.with_stem(filename)
        await self.move(path)

    async def delete_tags(self, tags: UnitIterable[Tags] = (), dry_run: bool = True) -> SyncResultTrack:
        """
        Remove tags from file.

        :param tags: Tags to remove.
        :param dry_run: Run function, but do not modify the file on the disk.
        :return: List of tags that have been removed.
        """
        result = self._writer.delete_tags(tags=tags, dry_run=dry_run)
        if Tags.IMAGES in result.updated:
            self.has_image = False
        return result

    def merge(self, track: Track, tags: UnitIterable[TrackField] = TrackField.ALL) -> None:
        """Set the tags of this track equal to the given ``track``. Give a list of ``tags`` to limit which are set"""
        tag_names = TrackField.__tags__ if tags == TrackField.ALL else set(TrackField.to_tags(tags))

        for tag in tag_names:  # merge on each tag
            if hasattr(track, tag):
                setattr(self, tag, deepcopy(track[tag]))

    def extract_images_to_file(self, output_folder: str | Path) -> int:
        """Reload the file, extract and save all embedded images from file. Returns the number of images extracted."""
        self._reader.file.load(self._reader.file.filename)

        images = self._reader.read_images()
        if images is None:
            return 0

        output_folder = Path(output_folder)
        if not output_folder.is_dir():
            raise UnexpectedPathError(output_folder, "Given path must be a directory")

        count = 0
        for i, image in enumerate(images):
            output_path = output_folder.joinpath(self.filename + f"_{str(i).zfill(2)}")
            output_path = output_path.with_suffix("." + image.format.lower().lstrip("."))

            output_path.parent.mkdir(parents=True, exist_ok=True)
            image.save(output_path)
            count += 1

        # to reduce memory usage, remove any embedded images from the loaded file
        self._writer.clear_loaded_images()

        return count

    def as_dict(self):
        attributes_extra = {"remote_source": self._reader.remote_source}
        return self._get_attributes() | attributes_extra

    def __hash__(self):
        # If a class overrides __eq__, it must override __hash__ alongside it.
        # https://stackoverflow.com/questions/74664008/python-typeerror-unhashable-type-when-inheriting-from-subclass-with-hash
        # https://github.com/python/cpython/issues/46488
        return super().__hash__()

    def __eq__(self, item: MusifyItem):
        if hasattr(item, "path"):
            return self.path == item.path
        return super().__eq__(item)

    def __copy__(self):
        """Copy object by reloading from the file object in memory"""
        new = self.__class__(file=self.path, remote_wrangler=self._reader.remote_wrangler)
        new._reader = self._reader
        new._writer = self._writer

        if self._reader.file.tags:
            new._refresh()
            # image is deleted from loaded file on refresh in initial run
            # set parameter manually here rather than rely on the 2nd refresh to set it
            new.has_image = self.has_image
            new.image_links = self.image_links
        else:  # file is not a real file, used in testing. Set shallow copy of attributes manually
            keys = [key for key in LocalTrack.__slots__ if key.lstrip("_") in dir(self)]
            for key in keys:
                setattr(new, key, copy(getattr(self, key)))

        return new

    def __deepcopy__(self, _: dict = None):
        """Deepcopy object by reloading from the file on disk and refreshing loaded metadata from it."""
        new = self.__class__(file=self.path, remote_wrangler=self._reader.remote_wrangler)

        file = mutagen.File(self.path) if self._reader.file.tags else self._reader.file
        new._reader = self._create_reader(file)
        new._writer = self._create_writer(file)

        new.refresh()
        return new

    def __setitem__(self, key: str | LocalTrackField, value: Any):
        if isinstance(key, LocalTrackField):
            try:
                key = next(iter(sorted(key.to_tag())))
            except StopIteration:
                key = key.name.lower()

        if not hasattr(self, key):
            raise MusifyKeyError(f"Given key is not a valid attribute of this item: {key}")

        attr = getattr(self, key)
        if isinstance(attr, property) and attr.fset is None:
            raise MusifyAttributeError(f"Cannot set values on the given key, it is protected: {key}")

        return setattr(self, key, value)

    def __or__(self, other: Track) -> Self:
        if not isinstance(other, Track):
            raise MusifyTypeError(
                f"Incorrect item given. Cannot merge with {other.__class__.__name__} as it is not a Track"
            )

        self_copy = copy(self)
        self_copy.merge(other, tags=TrackField.ALL)
        return self_copy

    def __ior__(self, other: Track) -> Self:
        if not isinstance(other, Track):
            raise MusifyTypeError(
                f"Incorrect item given. Cannot merge with {other.__class__.__name__} as it is not a Track"
            )

        self.merge(other, tags=TrackField.ALL)
        return self
