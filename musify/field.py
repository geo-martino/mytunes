## DEPRECATED

"""
All core :py:class:`Field` implementations relating to
core :py:class:`MusifyItem` and :py:class`MusifyCollection` implementations.
"""
from collections.abc import Sequence
from dataclasses import field, dataclass
from typing import Self

from aiorequestful.types import UnitIterable

from musify.types import MusifyEnum


class Field(MusifyEnum):
    """Base class for field names of an item."""

    @classmethod
    def from_name(cls, *names: str) -> list[Self]:
        """
        Returns all enums that match the given enum names

        :raise EnumNotFoundError: If a corresponding enum cannot be found.
        """
        return super().from_name(*names, fail_on_many=False)

    @classmethod
    def from_value(cls, *values: int) -> list[Self]:
        """
        Returns all enums that match the given enum values

        :raise EnumNotFoundError: If a corresponding enum cannot be found.
        """
        return super().from_value(*values, fail_on_many=False)


class Fields(Field):
    """
    All possible Field enums in this program.

    This is used to ensure all Field enum implementations have the same values for their enum names.
    """
    # all numbers relate to the number of the field value as mapped by MusicBee
    # changing these numbers will break all MusicBee functionality unless it is noted
    # that a mapping with a MusicBee field is not present for that enum

    ALL = 0
    NAME = 1000

    # tags/core properties
    TITLE = 65
    ARTIST = 32
    ARTISTS = 108
    ALBUM = 30  # MusicBee album ignoring articles like 'the' and 'a' etc.
    ALBUM_ARTIST = 31
    TRACK_NUMBER = 86
    TRACK_TOTAL = 87
    GENRES = 59
    DATE = 900  # no MusicBee mapping
    YEAR = 35
    MONTH = 901  # no MusicBee mapping
    DAY = 902  # no MusicBee mapping
    BPM = 85
    KEY = 903  # unknown MusicBee mapping
    DISC_NUMBER = 52
    DISC_TOTAL = 54
    COMPILATION = 904  # unknown MusicBee mapping
    COMMENTS = 44
    IMAGES = 905  # no MusicBee mapping
    LENGTH = 16
    RATING = 75
    COMPOSER = 43
    CONDUCTOR = 45
    PUBLISHER = 73

    # file properties
    PATH = 106
    FOLDER = 179
    FILENAME = 3
    EXT = 100
    SIZE = 7
    TYPE = 4
    CHANNELS = 8
    BIT_RATE = 10
    BIT_DEPTH = 183
    SAMPLE_RATE = 9

    # date properties
    DATE_CREATED = 921  # no MusicBee mapping
    DATE_MODIFIED = 11
    DATE_ADDED = 12
    LAST_PLAYED = 13

    # miscellaneous properties
    PLAY_COUNT = 14
    DESCRIPTION = 931  # no MusicBee mapping

    # remote properties
    URI = 941  # no MusicBee mapping
    USER_ID = 942  # no MusicBee mapping
    USER_NAME = 943  # no MusicBee mapping
    OWNER_ID = 944  # no MusicBee mapping
    OWNER_NAME = 945  # no MusicBee mapping
    FOLLOWERS = 946  # no MusicBee mapping


###########################################################################
## Tags
###########################################################################
@dataclass(frozen=True)
class TagMap:
    """Map of human-friendly tag name to ID3 tag ids for a file type"""
    # helpful for determining tags map: https://wiki.hydrogenaud.io/index.php?title=Tag_Mapping

    title: Sequence[str] = field(default=())
    artist: Sequence[str] = field(default=())
    album: Sequence[str] = field(default=())
    album_artist: Sequence[str] = field(default=())
    track_number: Sequence[str] = field(default=())
    track_total: Sequence[str] = field(default=())
    genres: Sequence[str] = field(default=())
    date: Sequence[str] = field(default=())
    year: Sequence[str] = field(default=())
    month: Sequence[str] = field(default=())
    day: Sequence[str] = field(default=())
    bpm: Sequence[str] = field(default=())
    key: Sequence[str] = field(default=())
    disc_number: Sequence[str] = field(default=())
    disc_total: Sequence[str] = field(default=())
    compilation: Sequence[str] = field(default=())
    comments: Sequence[str] = field(default=())
    images: Sequence[str] = field(default=())

    def __getitem__(self, key: str) -> Sequence[str]:
        """Safely get the value of a given attribute key, returning an empty string if the key is not found"""
        return getattr(self, key, [])


class TagField(Field):
    """Applies extra functionality to :py:class:`Field` for objects which contain modifiable tags"""

    __tags__: frozenset[str] = frozenset(list(TagMap.__annotations__.keys()) + ["uri"])

    @classmethod
    def all(cls, only_tags: bool = False) -> list[Self]:
        """
        Get all enums for this enum.
        When ``only_tags`` is True, returns only those enums that represent a tag for this TagField type.
        """
        enums = super().all()
        if not only_tags:
            return enums

        return list(sorted(cls.from_name(*cls.to_tags(enums)), key=lambda x: enums.index(x)))

    def to_tag(self) -> set[str]:
        """
        Returns all human-friendly tag names for the current enum value.

        Applies mapper to enums before returning as per :py:meth:`map`.
        This will only return tag names if they are found in :py:class:`TagMap`.
        """
        if self == Fields.ALL:
            return {tag.name.lower() for tag in super().all() if tag.name.lower() in self.__tags__}
        return {tag.name.lower() for tag in self.map(self) if tag.name.lower() in self.__tags__}

    @classmethod
    def to_tags(cls, tags: UnitIterable[Self]) -> set[str]:
        """
        Returns all human-friendly tag names for the given enum value.

        Applies mapper to enums before returning as per :py:meth:`map`.
        This will only return tag names if they are found in :py:class:`TagMap`.
        """
        if isinstance(tags, cls):
            return tags.to_tag()
        return {t for tag in tags for t in tag.to_tag()}


class TagFields(TagField):
    """
    All possible TagField enums in this program.

    This is used to ensure all TagField enum implementations have the same values for their enum names.
    """
    ALL = Fields.ALL.value
    NAME = Fields.NAME.value

    # tags/core properties
    TITLE = Fields.TITLE.value
    ARTIST = Fields.ARTIST.value
    ALBUM = Fields.ALBUM.value
    ALBUM_ARTIST = Fields.ALBUM_ARTIST.value
    TRACK_NUMBER = Fields.TRACK_NUMBER.value
    TRACK_TOTAL = Fields.TRACK_TOTAL.value
    GENRES = Fields.GENRES.value
    DATE = Fields.DATE.value
    YEAR = Fields.YEAR.value
    MONTH = Fields.MONTH.value
    DAY = Fields.DAY.value
    BPM = Fields.BPM.value
    KEY = Fields.KEY.value
    DISC_NUMBER = Fields.DISC_NUMBER.value
    DISC_TOTAL = Fields.DISC_TOTAL.value
    COMPILATION = Fields.COMPILATION.value
    COMMENTS = Fields.COMMENTS.value
    IMAGES = Fields.IMAGES.value
    LENGTH = Fields.LENGTH.value
    RATING = Fields.RATING.value
    COMPOSER = Fields.COMPOSER.value
    CONDUCTOR = Fields.CONDUCTOR.value
    PUBLISHER = Fields.PUBLISHER.value

    # file properties
    PATH = Fields.PATH.value
    FOLDER = Fields.FOLDER.value
    FILENAME = Fields.FILENAME.value
    EXT = Fields.EXT.value
    SIZE = Fields.SIZE.value
    TYPE = Fields.TYPE.value
    CHANNELS = Fields.CHANNELS.value
    BIT_RATE = Fields.BIT_RATE.value
    BIT_DEPTH = Fields.BIT_DEPTH.value
    SAMPLE_RATE = Fields.SAMPLE_RATE.value

    # date properties
    DATE_CREATED = Fields.DATE_CREATED.value
    DATE_MODIFIED = Fields.DATE_MODIFIED.value
    DATE_ADDED = Fields.DATE_ADDED.value
    LAST_PLAYED = Fields.LAST_PLAYED.value

    # miscellaneous properties
    PLAY_COUNT = Fields.PLAY_COUNT.value
    DESCRIPTION = Fields.DESCRIPTION.value

    # remote properties
    URI = Fields.URI.value
    USER_ID = Fields.USER_ID.value
    USER_NAME = Fields.USER_NAME.value
    OWNER_ID = Fields.OWNER_ID.value
    OWNER_NAME = Fields.OWNER_NAME.value
    FOLLOWERS = Fields.FOLLOWERS.value


ALL_FIELDS = frozenset(Fields.all())
ALL_TAG_FIELDS = frozenset(TagFields.all())


###########################################################################
## Object-specific fields
###########################################################################
class TrackFieldMixin(TagField):
    """Applies extra functionality to the TagField enum for TagField types relating to :py:class:`Track` types"""

    # noinspection PyUnresolvedReferences
    @classmethod
    def map(cls, enum: Self) -> list[Self]:
        if enum == cls.TRACK:
            return [cls.TRACK_NUMBER, cls.TRACK_TOTAL]
        elif enum == cls.DISC:
            return [cls.DISC_NUMBER, cls.DISC_TOTAL]
        elif enum == cls.DATE:
            return [cls.DATE, cls.YEAR, cls.MONTH, cls.DAY]
        return [enum]


class TrackField(TrackFieldMixin):
    """Represents all currently supported fields for objects of type :py:class:`Track`"""
    ALL = TagFields.ALL.value

    TITLE = TagFields.TITLE.value
    ARTIST = TagFields.ARTIST.value
    ALBUM = TagFields.ALBUM.value
    ALBUM_ARTIST = TagFields.ALBUM_ARTIST.value
    TRACK = TagFields.TRACK_NUMBER.value + 500
    TRACK_NUMBER = TagFields.TRACK_NUMBER.value
    TRACK_TOTAL = TagFields.TRACK_TOTAL.value
    GENRES = TagFields.GENRES.value
    DATE = TagFields.DATE.value
    YEAR = TagFields.YEAR.value
    MONTH = TagFields.MONTH.value
    DAY = TagFields.DAY.value
    BPM = TagFields.BPM.value
    KEY = TagFields.KEY.value
    DISC = TagFields.DISC_NUMBER.value + 500
    DISC_NUMBER = TagFields.DISC_NUMBER.value
    DISC_TOTAL = TagFields.DISC_TOTAL.value
    COMPILATION = TagFields.COMPILATION.value
    COMMENTS = TagFields.COMMENTS.value
    IMAGES = TagFields.IMAGES.value
    LENGTH = TagFields.LENGTH.value
    RATING = TagFields.RATING.value

    # remote properties
    URI = TagFields.URI.value


class PlaylistField(Field):
    """Represents all currently supported fields for objects of type :py:class:`Playlist`"""
    ALL = Fields.ALL.value

    # tags/core properties
    TRACK_TOTAL = Fields.TRACK_TOTAL.value
    IMAGES = Fields.IMAGES.value
    LENGTH = Fields.LENGTH.value

    # date properties
    DATE_CREATED = Fields.DATE_CREATED.value
    DATE_MODIFIED = Fields.DATE_MODIFIED.value

    # miscellaneous properties
    DESCRIPTION = Fields.DESCRIPTION.value


class FolderField(Field):
    """Represents all currently supported fields for objects of type :py:class:`Folder`"""
    ALL = Fields.ALL.value

    # tags/core properties
    TRACK_TOTAL = Fields.TRACK_TOTAL.value
    GENRES = Fields.GENRES.value
    IMAGES = Fields.IMAGES.value
    COMPILATION = Fields.COMPILATION.value
    LENGTH = Fields.LENGTH.value

    # file properties
    FOLDER = Fields.FOLDER.value


class AlbumField(Field):
    """Represents all currently supported fields for objects of type :py:class:`Album`"""
    ALL = Fields.ALL.value

    # tags/core properties
    ARTIST = Fields.ARTIST.value
    ALBUM = Fields.ALBUM.value
    ALBUM_ARTIST = Fields.ALBUM_ARTIST.value
    TRACK_TOTAL = Fields.TRACK_TOTAL.value
    GENRES = Fields.GENRES.value
    DATE = TagFields.DATE.value
    YEAR = TagFields.YEAR.value
    MONTH = TagFields.MONTH.value
    DAY = TagFields.DAY.value
    DISC_TOTAL = Fields.DISC_TOTAL.value
    COMPILATION = Fields.COMPILATION.value
    IMAGES = Fields.IMAGES.value
    LENGTH = Fields.LENGTH.value
    RATING = Fields.RATING.value


class ArtistField(Field):
    """Represents all currently supported fields for objects of type :py:class:`Artist`"""
    ALL = Fields.ALL.value

    # tags/core properties
    ARTIST = Fields.ARTIST.value
    TRACK_TOTAL = Fields.TRACK_TOTAL.value
    GENRES = Fields.GENRES.value
    IMAGES = Fields.IMAGES.value
    LENGTH = Fields.LENGTH.value
    RATING = Fields.RATING.value
