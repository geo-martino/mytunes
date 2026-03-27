"""
The core abstract implementations of :py:class:`MusifyItem` and :py:class:`MusifyCollection` classes.
"""
from __future__ import annotations

import datetime
from abc import ABCMeta, abstractmethod
from collections.abc import Collection, Mapping, Iterable
from copy import deepcopy
from pathlib import Path
from typing import Self

from yarl import URL

from musify.base import MusifyItem, HasLength
from musify.exception import MusifyTypeError
from musify.libraries.core.collection import MusifyCollection
from musify.libraries.remote.core.types import RemoteObjectType
from musify.utils import classproperty


class Track(MusifyItem, HasLength, metaclass=ABCMeta):
    """Represents a track including its metadata/tags/properties."""

    __slots__ = ()
    __attributes_ignore__ = ("name",)

    # noinspection PyMethodParameters
    @classproperty
    def kind(cls) -> RemoteObjectType:
        """The type of remote object associated with this class"""
        return RemoteObjectType.TRACK

    @property
    def name(self) -> str:
        """This track's title"""
        return self.title

    @property
    @abstractmethod
    def title(self) -> str | None:
        """This track's title"""
        raise NotImplementedError

    @property
    @abstractmethod
    def artist(self) -> str | None:
        """Joined string representation of all artists featured on this track"""
        raise NotImplementedError

    @property
    @abstractmethod
    def artists(self) -> list[str | Artist]:
        """List of all artists featured on this track."""
        raise NotImplementedError

    @property
    @abstractmethod
    def album(self) -> str | None:
        """The album this track is featured on"""
        raise NotImplementedError

    @property
    @abstractmethod
    def album_artist(self) -> str | None:
        """The artist of the album this track is featured on"""
        raise NotImplementedError

    @property
    @abstractmethod
    def track_number(self) -> int | None:
        """The position this track has on the album it is featured on"""
        raise NotImplementedError

    @property
    @abstractmethod
    def track_total(self) -> int | None:
        """The track number of tracks on the album this track is featured on"""
        raise NotImplementedError

    @property
    @abstractmethod
    def genres(self) -> list[str] | None:
        """List of genres associated with this track"""
        raise NotImplementedError

    @property
    def date(self) -> datetime.date | None:
        """A :py:class:`date` object representing the release date of this track"""
        if self.year and self.month and self.day:
            return datetime.date(self.year, self.month, self.day)

    @property
    @abstractmethod
    def year(self) -> int | None:
        """The year this track was released"""
        raise NotImplementedError

    @property
    @abstractmethod
    def month(self) -> int | None:
        """The month this track was released"""
        raise NotImplementedError

    @property
    @abstractmethod
    def day(self) -> int | None:
        """The day this track was released"""
        raise NotImplementedError

    @property
    @abstractmethod
    def bpm(self) -> float | None:
        """The tempo of this track"""
        raise NotImplementedError

    @property
    @abstractmethod
    def key(self) -> str | None:
        """The key of this track in alphabetical musical notation format"""
        raise NotImplementedError

    @property
    @abstractmethod
    def disc_number(self) -> int | None:
        """The number of the disc from the album this track is featured on"""
        raise NotImplementedError

    @property
    @abstractmethod
    def disc_total(self) -> int | None:
        """The total number the discs from the album this track is featured on"""
        raise NotImplementedError

    @property
    @abstractmethod
    def compilation(self) -> bool | None:
        """Is the album this track is featured on a compilation"""
        raise NotImplementedError

    @property
    @abstractmethod
    def comments(self) -> list[str] | None:
        """Comments associated with this track set by the user"""
        raise NotImplementedError

    @property
    @abstractmethod
    def image_links(self) -> dict[str, str | Path | URL]:
        """
        The images associated with the album this track is featured on in the form ``{<image name/type>: <image link>}``
        """
        raise NotImplementedError

    @property
    def has_image(self) -> bool:
        """Does the album this track is associated with have an image"""
        return len(self.image_links) > 0

    @property
    @abstractmethod
    def length(self) -> float | None:
        """Total duration of this track in seconds"""
        raise NotImplementedError

    @property
    @abstractmethod
    def rating(self) -> float | None:
        """The rating for this track"""
        raise NotImplementedError

    def __hash__(self):
        # If a class overrides __eq__, it must override __hash__ alongside it.
        # https://stackoverflow.com/questions/74664008/python-typeerror-unhashable-type-when-inheriting-from-subclass-with-hash
        # https://github.com/python/cpython/issues/46488
        return super().__hash__()

    def __eq__(self, item: Track):
        if super().__eq__(item):  # attempt to match on URI first
            return True

        if not isinstance(item, Track):
            return False

        # match on track properties as last resort
        self_artists = {artist if isinstance(artist, str) else artist.name for artist in self.artists}
        item_artists = {artist if isinstance(artist, str) else artist.name for artist in item.artists}

        return self.title == item.title and self_artists & item_artists and self.album == item.album


class Playlist[T: Track](MusifyCollection[T], metaclass=ABCMeta):
    """A playlist of items and their derived properties/objects."""

    __slots__ = ()
    __attributes_classes__ = MusifyCollection
    __attributes_ignore__ = ("items",)

    # noinspection PyMethodParameters
    @classproperty
    def kind(cls) -> RemoteObjectType:
        """The type of remote object associated with this class"""
        return RemoteObjectType.PLAYLIST

    @property
    @abstractmethod
    def name(self):
        """The name of this playlist"""
        raise NotImplementedError

    @property
    @abstractmethod
    def description(self) -> str | None:
        """Description of this playlist"""
        raise NotImplementedError

    @property
    def items(self):
        """The tracks in this collection"""
        return self.tracks

    @property
    @abstractmethod
    def tracks(self) -> list[T]:
        """The tracks in this playlist"""
        raise NotImplementedError

    @property
    def track_total(self) -> int:
        """The total number of tracks in this playlist"""
        return len(self)

    @property
    @abstractmethod
    def image_links(self) -> dict[str, str]:
        """The images associated with this playlist in the form ``{<image name/type>: <image link>}``"""
        raise NotImplementedError

    @property
    def has_image(self) -> bool:
        """Does this playlist have an image"""
        return len(self.image_links) > 0

    @property
    def length(self):
        """Total duration of all tracks in this playlist in seconds"""
        lengths = {track.length for track in self.tracks}
        return sum(lengths) if lengths else None

    @property
    @abstractmethod
    def date_created(self) -> datetime.datetime | None:
        """:py:class:`datetime.datetime` object representing when the playlist was created"""
        raise NotImplementedError

    @property
    @abstractmethod
    def date_modified(self) -> datetime.datetime | None:
        """:py:class:`datetime.datetime` object representing when the playlist was last modified"""
        raise NotImplementedError

    def merge(self, other: Iterable[T], reference: Self | None = None) -> None:
        """
        Merge tracks in this playlist with another collection, synchronising tracks between the two.
        Only modifies this playlist.

        Sort order is not preserved when merging.
        Any items that need to be added to this playlist will be added at the end of the playlist.
        Duplicates that are present in the ``other`` collection are filtered out by default.

        :param other: The collection of items to merge onto this playlist.
        :param reference: Optionally, provide a reference playlist to compare both the current playlist
            and the ``other`` items to. The function will determine tracks to remove from
            this playlist based on the reference. Useful for using this function as a synchronizer
            where the reference refers to the playlist at the previous sync.
        """
        if not self._validate_item_type(other):
            raise MusifyTypeError([type(i).__name__ for i in other])

        if reference is None:
            self.extend(self.outer_difference(other), allow_duplicates=False)
            return

        for item in reference:
            if item not in other and item in self:
                self.remove(item)

        self.extend(reference.outer_difference(other), allow_duplicates=False)

    def __or__(self, other: Playlist[T]) -> Self:
        if not isinstance(other, self.__class__):
            raise MusifyTypeError(
                f"Incorrect item given. Cannot merge with {other.__class__.__name__} "
                f"as it is not a {self.__class__.__name__}"
            )

        self_copy = deepcopy(self)
        self_copy.merge(other)
        return self_copy

    def __ior__(self, other: Playlist[T]) -> Self:
        if not isinstance(other, self.__class__):
            raise MusifyTypeError(
                f"Incorrect item given. Cannot merge with {other.__class__.__name__} "
                f"as it is not a {self.__class__.__name__}"
            )

        self.merge(other)
        return self


type LibraryMergeType[T] = Library[T] | Collection[Playlist[T]] | Mapping[str, Playlist[T]]


class Library[T: Track](MusifyCollection[T], metaclass=ABCMeta):
    """A library of items and playlists and other object types."""

    __slots__ = ()
    __attributes_classes__ = MusifyCollection
    __attributes_ignore__ = ("items",)

    @property
    @abstractmethod
    def name(self):
        """The library name"""
        raise NotImplementedError

    # noinspection PyMethodParameters
    @classproperty
    def source(cls) -> str:
        """The type of library loaded"""
        return cls.__name__.replace("Library", "")

    @property
    def items(self):
        """The tracks in this collection"""
        return self.tracks

    @property
    def length(self):
        """Total duration of all tracks in this library in seconds"""
        lengths = {track.length for track in self.tracks}
        return sum(lengths) if lengths else None

    @property
    @abstractmethod
    def tracks(self) -> list[T]:
        """The tracks in this library"""
        raise NotImplementedError

    @property
    def track_total(self) -> int:
        """The total number of tracks in this library"""
        return len(self)

    @property
    def tracks_in_playlists(self) -> set[T]:
        """All unique tracks from all playlists in this library"""
        return {track for pl in self.playlists.values() for track in pl}

    @property
    @abstractmethod
    def playlists(self) -> dict[str, Playlist[T]]:
        """The playlists in this library"""
        raise NotImplementedError

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

    def merge_playlists(self, playlists: LibraryMergeType[T], reference: LibraryMergeType[T] | None = None) -> None:
        """
        Merge playlists from given list/map/library to this library.

        See :py:meth:`.Playlist.merge` for more info.

        :param playlists: The playlists to merge onto this library's playlists.
            If a given playlist is not found in this library, simply add the playlist to this library.
        :param reference: Optionally, provide a reference playlist to compare both the current playlist
            and the ``other`` items to. The function will determine tracks to remove from
            this playlist based on the reference. Useful for using this function as a synchronizer
            where the reference refers to the playlist at the previous sync.
        """
        def get_playlists_map(value: LibraryMergeType[T]) -> Mapping[str, Playlist[T]]:
            """Reformat the input playlist values to map"""
            if isinstance(value, Mapping):
                return value
            elif isinstance(value, Library):
                return value.playlists
            elif isinstance(value, Collection):
                return {pl.name: pl for pl in value}
            raise MusifyTypeError(f"Unrecognised input type: {value.__class__.__name__}")

        playlists = get_playlists_map(playlists)
        reference = get_playlists_map(reference) if reference is not None else {}

        for name, playlist in playlists.items():
            if name not in self.playlists:
                self.playlists[name] = deepcopy(playlist)
                continue

            self.playlists[name].merge(playlist, reference=reference.get(name))


class Folder[T: Track](MusifyCollection[T], metaclass=ABCMeta):
    """
    A folder of items and their derived properties/objects
    """

    __slots__ = ()
    __attributes_classes__ = MusifyCollection
    __attributes_ignore__ = ("name", "items")

    @property
    @abstractmethod
    def name(self):
        """The folder name"""
        raise NotImplementedError

    @property
    def folder(self) -> str:
        """The folder name"""
        return self.name

    @property
    def items(self):
        """The tracks in this collection"""
        return self.tracks

    @property
    @abstractmethod
    def tracks(self):
        """The tracks in this folder"""
        raise NotImplementedError

    @property
    @abstractmethod
    def artists(self) -> list[str]:
        """List of artists ordered by frequency of appearance on the tracks in this folder"""
        raise NotImplementedError

    @property
    @abstractmethod
    def albums(self) -> list[str]:
        """List of albums ordered by frequency of appearance on the tracks in this folder"""
        raise NotImplementedError

    @property
    def track_total(self) -> int:
        """The total number of tracks in this folder"""
        return len(self)

    @property
    @abstractmethod
    def genres(self) -> list[str]:
        """List of genres ordered by frequency of appearance on the tracks in this folder"""
        raise NotImplementedError

    @property
    @abstractmethod
    def compilation(self) -> bool:
        """Is this folder a compilation"""
        raise NotImplementedError

    @property
    def length(self):
        """Total duration of all tracks in this folder in seconds"""
        lengths = {track.length for track in self.tracks}
        return sum(lengths) if lengths else None


class Album[T: Track](MusifyCollection[T], metaclass=ABCMeta):
    """An album of items and their derived properties/objects."""

    __slots__ = ()
    __attributes_classes__ = MusifyCollection
    __attributes_ignore__ = ("name", "items")

    # noinspection PyMethodParameters
    @classproperty
    def kind(cls) -> RemoteObjectType:
        """The type of remote object associated with this class"""
        return RemoteObjectType.ALBUM

    @property
    @abstractmethod
    def name(self) -> str:
        """The album name"""
        raise NotImplementedError

    @property
    def items(self):
        """The tracks in this collection"""
        return self.tracks

    @property
    def album(self) -> str:
        """The album name"""
        return self.name

    @property
    @abstractmethod
    def tracks(self) -> list[T]:
        """The tracks on this album"""
        raise NotImplementedError

    @property
    def artist(self) -> str:
        """Joined string representation of all artists on this album ordered by frequency of appearance"""
        return self.tag_sep.join(self.artists)

    @property
    @abstractmethod
    def artists(self) -> list[str | Artist]:
        """List of artists ordered by frequency of appearance on the tracks on this album"""
        raise NotImplementedError

    @property
    @abstractmethod
    def album_artist(self) -> str | None:
        """The album artist for this album"""
        raise NotImplementedError

    @property
    def track_total(self) -> int:
        """The total number of tracks on this album"""
        return len(self)

    @property
    @abstractmethod
    def genres(self) -> list[str]:
        """List of genres ordered by frequency of appearance on the tracks on this album"""
        raise NotImplementedError

    @property
    def date(self) -> datetime.date | None:
        """A :py:class:`date` object representing the release date of this album"""
        if self.year and self.month and self.day:
            return datetime.date(self.year, self.month, self.day)

    @property
    @abstractmethod
    def year(self) -> int | None:
        """The year this album was released"""
        raise NotImplementedError

    @property
    @abstractmethod
    def month(self) -> int | None:
        """The month this album was released"""
        raise NotImplementedError

    @property
    @abstractmethod
    def day(self) -> int | None:
        """The day this album was released"""
        raise NotImplementedError

    @property
    def disc_total(self) -> int | None:
        """The highest value of disc number on this album"""
        disc_numbers = {track.disc_number for track in self.tracks if track.disc_number}
        return max(disc_numbers) if disc_numbers else None

    @property
    @abstractmethod
    def compilation(self) -> bool:
        """Is this album a compilation"""
        raise NotImplementedError

    @property
    @abstractmethod
    def image_links(self) -> dict[str, str]:
        """The images associated with this album in the form ``{<image name/type>: <image link>}``"""
        raise NotImplementedError

    @property
    def has_image(self) -> bool:
        """Does this album have an image"""
        return len(self.image_links) > 0

    @property
    def length(self):
        """Total duration of all tracks on this album in seconds"""
        lengths = {track.length for track in self.tracks}
        return sum(lengths) if lengths else None

    @property
    @abstractmethod
    def rating(self) -> float | None:
        """Rating of this album"""
        raise NotImplementedError


class Artist[T: (Track, Album)](MusifyCollection[T], metaclass=ABCMeta):
    """An artist of items and their derived properties/objects."""

    __slots__ = ()
    __attributes_classes__ = MusifyCollection
    __attributes_ignore__ = ("name", "items")

    # noinspection PyMethodParameters
    @classproperty
    def kind(cls) -> RemoteObjectType:
        """The type of remote object associated with this class"""
        return RemoteObjectType.ARTIST

    @property
    @abstractmethod
    def name(self):
        """The artist name"""
        raise NotImplementedError

    @property
    def items(self):
        """The tracks in this collection"""
        return self.tracks

    @property
    def artist(self) -> str:
        """The artist name"""
        return self.name

    @property
    @abstractmethod
    def tracks(self) -> list[T]:
        """The tracks by this artist"""
        raise NotImplementedError

    @property
    @abstractmethod
    def artists(self) -> list[str]:
        """List of other artists ordered by frequency of appearance on the albums by this artist"""
        raise NotImplementedError

    @property
    @abstractmethod
    def albums(self) -> list[str | Album]:
        """List of albums ordered by frequency of appearance on the tracks by this artist"""
        raise NotImplementedError

    @property
    def track_total(self) -> int:
        """The total number of tracks by this artist"""
        return len(self)

    @property
    @abstractmethod
    def genres(self) -> list[str]:
        """List of genres for this artist"""
        raise NotImplementedError

    @property
    def length(self):
        """Total duration of all tracks by this artist in seconds"""
        lengths = {track.length for track in self.tracks}
        return sum(lengths) if lengths else None

    @property
    @abstractmethod
    def rating(self) -> int | None:
        """The popularity of this artist"""
        raise NotImplementedError


class Genre[T: Track](MusifyCollection[T], metaclass=ABCMeta):
    """A genre of items and their derived properties/objects."""

    __slots__ = ()
    __attributes_classes__ = MusifyCollection
    __attributes_ignore__ = ("name", "items")

    @property
    @abstractmethod
    def name(self):
        """The genre"""
        raise NotImplementedError

    @property
    def items(self):
        """The tracks in this collection"""
        return self.tracks

    @property
    def genre(self) -> str:
        """The genre"""
        return self.name

    @property
    @abstractmethod
    def tracks(self) -> list[T]:
        """The tracks for this genre"""
        raise NotImplementedError

    @property
    @abstractmethod
    def artists(self) -> list[str]:
        """List of artists ordered by frequency of appearance on the tracks for this genre"""
        raise NotImplementedError

    @property
    @abstractmethod
    def albums(self) -> list[str]:
        """List of albums ordered by frequency of appearance on the tracks for this genre"""
        raise NotImplementedError

    @property
    @abstractmethod
    def related_genres(self) -> list[str]:
        """List of related genres ordered by frequency of appearance on the tracks for this genre"""
        raise NotImplementedError

    @property
    def length(self):
        """Total duration of all tracks with this genre in seconds"""
        lengths = {track.length for track in self.tracks}
        return sum(lengths) if lengths else None
