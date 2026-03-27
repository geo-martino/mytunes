"""
Implements all collection types for a local library.
"""
from __future__ import annotations

import asyncio
import logging
import sys
from abc import ABCMeta, abstractmethod
from collections.abc import Mapping, Collection, Iterable, Container
from datetime import datetime
from pathlib import Path
from typing import Any, Self

from aiorequestful.types import UnitCollection, UnitIterable

from musify.field import Fields, TagField, TagFields
from musify.file.exception import UnexpectedPathError
from musify.libraries.core.collection import MusifyCollection
from musify.libraries.core.object import Track, Library, Folder, Album, Artist, Genre
from musify.libraries.local.base import LocalItem
from musify.libraries.local.exception import LocalCollectionError
from musify.libraries.local.track import LocalTrack, SyncResultTrack, load_track, TRACK_FILETYPES
from musify.libraries.local.track.field import LocalTrackField
from musify.libraries.remote.core.wrangle import RemoteDataWrangler
from musify.logger import MusifyLogger
from musify.utils import get_most_common_values, to_collection, align_string, get_max_width

_max_str = "z" * 50


class LocalCollection[T: LocalTrack](MusifyCollection[T], metaclass=ABCMeta):
    """
    Generic class for storing a collection of local tracks.

    :param remote_wrangler: Optionally, provide a :py:class:`RemoteDataWrangler` object for processing URIs on items.
        If given, the wrangler can be used when calling __get_item__ to get an item from the collection from its URI.
    """

    __slots__ = ("logger", "remote_wrangler")
    __attributes_ignore__ = ("track_total", "last_modified")

    @staticmethod
    def _validate_item_type(items: Any | Iterable[Any]) -> bool:
        if isinstance(items, Iterable):
            return all(isinstance(item, LocalItem) for item in items)
        return isinstance(items, LocalItem)

    @property
    def items(self) -> list[T]:
        """The tracks in this collection"""
        return self.tracks

    @property
    @abstractmethod
    def tracks(self) -> list[T]:
        """The tracks in this collection"""
        raise NotImplementedError

    @property
    def track_total(self) -> int:
        """The total number of tracks in this collection"""
        return len(self)

    @property
    def last_modified(self) -> datetime:
        """Timestamp of the last modified track in this collection"""
        sort = sorted(filter(lambda t: t.date_modified, self.tracks), key=lambda t: t.date_modified, reverse=True)
        # None condition will only be returned when using dummy tracks in tests therefore not included in typing
        return sort[0].date_modified if sort else None

    @property
    def last_added(self) -> datetime | None:
        """Timestamp of the track last added to the library in this collection"""
        sort = sorted(filter(lambda t: t.date_added, self.tracks), key=lambda t: t.date_added, reverse=True)
        return sort[0].date_added if sort else None

    @property
    def last_played(self) -> datetime | None:
        """Timestamp of the last played track in this collection"""
        sort = sorted(filter(lambda t: t.last_played, self.tracks), key=lambda t: t.last_played, reverse=True)
        return sort[0].last_played if sort else None

    @property
    def play_count(self) -> int:
        """Total number of plays of all tracks in this collection"""
        return sum(track.play_count for track in self.tracks if track.play_count)

    def __init__(self, remote_wrangler: RemoteDataWrangler = None):
        super().__init__()

        # noinspection PyTypeChecker
        #: The :py:class:`MusifyLogger` for this  object
        self.logger: MusifyLogger = logging.getLogger(__name__)
        #: A :py:class:`RemoteDataWrangler` object for processing remote data
        self.remote_wrangler = remote_wrangler

    async def save_tracks(
            self,
            tags: UnitIterable[LocalTrackField] = LocalTrackField.ALL,
            replace: bool = False,
            dry_run: bool = True
    ) -> dict[T, SyncResultTrack]:
        """
        Saves the tags of all tracks in this collection. Use arguments from :py:func:`LocalTrack.save`

        :param tags: Tags to be updated.
        :param replace: Destructively replace tags in each file.
        :param dry_run: Run function, but do not modify the file on the disk.
        :return: A map of the :py:class:`LocalTrack` saved to its result as a :py:class:`SyncResultTrack` object
            only for tracks that were saved or would have been saved in the case of a dry run.
        """
        async def _save_track(track: T) -> tuple[T, SyncResultTrack]:
            return track, await track.save(tags=tags, replace=replace, dry_run=dry_run)

        # WARNING: making this run asynchronously will break tqdm; bar will get stuck after 1-2 ticks
        bar = self.logger.get_synchronous_iterator(
            self.tracks, desc="Updating tracks", unit="tracks"
        )
        results = dict([await _save_track(track) for track in bar])
        return {track: result for track, result in results.items() if result.saved or result.updated}

    def log_save_tracks_result(self, results: Mapping[T, SyncResultTrack], log_values: bool = False) -> None:
        """
        Log stats from the results of a ``save_tracks`` operation

        :param results: The results to log.
        :param log_values: Log the values of the track's tags.
        """
        if not results:
            return

        max_width = get_max_width([track.path for track in results], max_width=80)

        self.logger.stat("\33[1;96mSaved tags to the following tracks: \33[0m")
        for track, result in results.items():
            saved = "\33[92mSAVED" if result.saved else "\33[91mNOT SAVED"
            if log_values:
                tags = ' | '.join(
                    "\33[94m" + (
                        f"{tag.name}\33[97m=\33[34m{track[tag]}" if tag != LocalTrackField.PATH else tag.name
                    ) + "\33[0m"
                    for tag in result.updated
                )
            else:
                tags = "\33[94m" + ', '.join(tag.name for tag in result.updated)

            if not tags:
                tags = "No tags updated"

            self.logger.stat(
                f"\33[97m{align_string(track.path, max_width=max_width, truncate_left=True)} \33[0m| "
                f"{saved} \33[0m| \33[94m{tags} \33[0m"
            )

    def merge_tracks(self, tracks: Collection[Track], tags: UnitIterable[TagField] = Fields.ALL) -> None:
        """
        Merge this collection with another collection or list of items
        by performing an inner join on a given set of tags

        :param tracks: List of items or :py:class:`MusifyCollection` to merge with
        :param tags: List of tags to merge on.
        """
        # noinspection PyTypeChecker
        tag_names = set(TagField.__tags__) if tags == Fields.ALL else set(TagField.to_tags(tags))
        tag_order = [tag for field in TagFields.all(only_tags=True) for tag in field.to_tag()]
        tag_names = sorted(tag_names, key=lambda x: tag_order.index(x))

        if isinstance(self, Library | LocalCollection):  # log status message and use progress bar for libraries
            self.logger.info(
                f"\33[1;95m  >\33[1;97m "
                f"Merging library of {len(self)} items with {len(tracks)} items on tags: "
                f"\33[0;90m{', '.join(tag_names)}\33[0m"
            )
            tracks = self.logger.get_synchronous_iterator(tracks, desc="Merging library", unit="tracks")

        tags = to_collection(tags)
        if Fields.IMAGES in tags or Fields.ALL in tags:
            tag_names.append("image_links")

        for track in tracks:  # perform the merge
            track_in_collection: T = next((t for t in self.tracks if t == track), None)
            if not track_in_collection:  # skip if the item does not exist in this collection
                continue

            for tag in tag_names:  # merge on each tag
                if hasattr(track, tag):
                    track_in_collection[tag] = track[tag]

        if isinstance(self, Library | LocalCollection):
            self.logger.print_line()


class BasicLocalCollection[T: LocalTrack](LocalCollection[T]):

    __slots__ = ("_name", "_tracks")

    @property
    def name(self):
        """The name of this collection"""
        return self._name

    @property
    def tracks(self) -> list[T]:
        return self._tracks

    @property
    def length(self):
        lengths = {getattr(item, "length", None) for item in self.items}
        return sum({length for length in lengths if length}) if lengths else None

    def __init__(self, name: str, tracks: Collection[T], remote_wrangler: RemoteDataWrangler = None):
        super().__init__(remote_wrangler=remote_wrangler)
        self._name = name
        self._tracks = to_collection(tracks, list)


class LocalCollectionFiltered[T: LocalItem](LocalCollection[T], metaclass=ABCMeta):
    """
    Generic class for storing and filtering on a collection of local tracks
    with methods for enriching the attributes of this object from the attributes of the collection of tracks

    :param tracks: A list of loaded tracks.
    :param name: The name of this collection.
        If given, the object only stores tracks that match the name given on the attribute of this object.
        If None, the list of tracks given are taken to be all the tracks contained in this collection.
    :raise LocalCollectionError: If the given tracks contain more than one unique value
        for the attribute of this collection when name is None.
    :param remote_wrangler: Optionally, provide a :py:class:`RemoteDataWrangler` object for processing URIs on tracks.
        If given, the wrangler can be used when calling __get_item__ to get an item from the collection from its URI.
    """

    __slots__ = ("_tag_key", "_name", "_tracks")

    @property
    def name(self):
        """The name of the key property of this collection"""
        return self._name

    @property
    def tracks(self):
        return self._tracks

    @property
    def artists(self) -> list[str]:
        """List of artists ordered by frequency of appearance on the tracks in this collection"""
        return get_most_common_values(track.artist for track in self.tracks if track.artist)

    def __init__(
            self,
            tracks: Collection[T],
            name: str | None = None,
            remote_wrangler: RemoteDataWrangler = None
    ):
        super().__init__(remote_wrangler=remote_wrangler)
        if len(tracks) == 0:
            raise LocalCollectionError("No tracks were given")

        # get the tag key dynamically from the name of this class
        self._tag_key = self._pascal_to_snake(self.__class__.__name__.removeprefix("Local"))

        if name is None:  # attempt to determine the name of this collection from the given tracks
            names: list[UnitCollection[str]] = [track[self._tag_key] for track in tracks if track[self._tag_key]]
            names: set[str] = {(n for n in name) if isinstance(name, (list, set, tuple)) else name for name in names}

            if len(names) == 0:  # no valid name found
                raise LocalCollectionError(f"No {self._tag_key.rstrip('s')}s found in the given tracks")
            elif len(names) != 1:  # too many names found
                raise LocalCollectionError(
                    f"Too many {self._tag_key.rstrip('s')}s found in the given tracks. "
                    f"Only provide tracks from the same {self._tag_key.rstrip('s')}."
                )

            self._name: str = names.pop()
            self._tracks: list[T] = to_collection(tracks, list)
        else:  # match tracks with a tag equal to the given name for this collection
            self._name: str = name
            self._tracks: list[T] = self._get_matching_tracks(tracks)

    def _get_matching_tracks(self, tracks: Iterable[T]) -> list[T]:
        """Get a list of tracks that match this collection's name"""
        matched: list[T] = []
        for track in tracks:
            value = track[self._tag_key]
            if isinstance(value, str) and self.name == value:
                matched.append(track)
            elif isinstance(value, Container) and self.name in value:
                matched.append(track)

        return matched


class LocalFolder(LocalCollectionFiltered[LocalTrack], Folder[LocalTrack]):
    """
    Object representing a collection of tracks in a folder on the local drive.

    :param tracks: A list of loaded tracks.
    :param name: The name of this folder.
        If given, the object only stores tracks that match the folder ``name`` given.
        If None, the list of tracks given are taken to be all the tracks contained in this folder.
    :param remote_wrangler: Optionally, provide a :py:class:`RemoteDataWrangler` object for processing URIs on tracks.
        If given, the wrangler can be used when calling __get_item__ to get an item from the collection from its URI.
    :raise LocalCollectionError: If the given tracks contain more than one unique value for
        ``folder`` when name is None.
    """

    __slots__ = ()
    __attributes_classes__ = (Folder, LocalCollection)

    @property
    def albums(self):
        return get_most_common_values(track.album for track in self.tracks if track.album)

    @property
    def genres(self) -> list[str]:
        """List of genres ordered by frequency of appearance on the tracks in this collection"""
        genres = (genre for track in self.tracks for genre in (track.genres if track.genres else []))
        return get_most_common_values(genres)

    @property
    def compilation(self):
        """Folder is a compilation if over 50% of tracks are marked as compilation"""
        return (sum(track.compilation is True for track in self.tracks) / len(self.tracks)) > 0.5

    def __init__(
            self,
            tracks: Collection[LocalTrack] = (),
            name: str | None = None,
            remote_wrangler: RemoteDataWrangler = None
    ):
        super().__init__(tracks=tracks, name=name, remote_wrangler=remote_wrangler)
        self.tracks.sort(key=lambda x: x.filename or _max_str)

    @classmethod
    async def load_folder(cls, path: str | Path | None, remote_wrangler: RemoteDataWrangler = None) -> Self:
        """
        Load tracks in a folder at the given ``path``.

        :param path: The path of the folder to load.
        :param remote_wrangler: Optionally, provide a :py:class:`RemoteDataWrangler` object
            for processing URIs on tracks. If given, the wrangler can be used when calling __get_item__
            to get an item from the collection from its URI.
        """
        if not path.is_dir():
            raise UnexpectedPathError(path, "Path must be a directory")

        # load tracks in the folder
        tasks = asyncio.gather(*[load_track(p) for p in path.glob("*") if p.suffix in TRACK_FILETYPES])
        return cls(tracks=await tasks, name=path.name, remote_wrangler=remote_wrangler)


class LocalAlbum(LocalCollectionFiltered[LocalTrack], Album[LocalTrack]):
    """
    Object representing a collection of tracks of an album.

    :param tracks: A list of loaded tracks.
    :param name: The name of this album.
        If given, the object only stores tracks that match the album ``name`` given.
        If None, the list of tracks given are taken to be all the tracks for this album.
    :param remote_wrangler: Optionally, provide a :py:class:`RemoteDataWrangler` object for processing URIs on tracks.
        If given, the wrangler can be used when calling __get_item__ to get an item from the collection from its URI.
    :raise LocalCollectionError: If the given tracks contain more than one unique value for
        ``album`` when name is None.
    """

    __slots__ = ("_image_links",)
    __attributes_classes__ = (Album, LocalCollection)

    @property
    def album_artist(self):
        """The most common artist on this album"""
        artists = get_most_common_values(artist for track in self.tracks if track.artist for artist in track.artists)
        return artists[0] if artists else None

    @property
    def genres(self) -> list[str]:
        """List of genres ordered by frequency of appearance on the tracks in this collection"""
        genres = (genre for track in self.tracks for genre in (track.genres if track.genres else []))
        return get_most_common_values(genres)

    @property
    def date(self):
        """
        A :py:class:`date` object representing the release date of this album.
        Determined by the most common release date of all tracks on this album.
        """
        values = get_most_common_values(track.date for track in self.tracks if track.date)
        return values[0] if values else None

    @property
    def year(self):
        """The most common release year of all tracks on this album"""
        values = get_most_common_values(track.year for track in self.tracks if track.year)
        return values[0] if values else None

    @property
    def month(self):
        """The most common release month of all tracks on this album"""
        values = get_most_common_values(
            (track.year, track.month) for track in self.tracks if track.year and track.month
        )
        return values[0][1] if values else None

    @property
    def day(self):
        """The most common release day of all tracks on this album"""
        values = get_most_common_values(
            (track.year, track.month, track.day) for track in self.tracks if track.year and track.month and track.day
        )
        return values[0][2] if values else None

    @property
    def compilation(self):
        """Album is a compilation if over 50% of tracks are marked as compilation"""
        return (sum(track.compilation is True for track in self.tracks) / len(self.tracks)) > 0.5

    @property
    def image_links(self):
        return self._image_links

    @property
    def has_image(self):
        return any(track.has_image for track in self.tracks)

    @property
    def rating(self):
        """Average rating of all tracks on this album"""
        ratings = tuple(track.rating for track in self.tracks if track.rating is not None)
        return sum(ratings) / len(ratings) if len(ratings) > 0 else None

    def __init__(
            self, tracks: Collection[LocalTrack], name: str | None = None, remote_wrangler: RemoteDataWrangler = None
    ):
        super().__init__(tracks=tracks, name=name, remote_wrangler=remote_wrangler)
        self.tracks.sort(
            key=lambda x: (x.disc_number or sys.maxsize, x.track_number or sys.maxsize, x.filename or _max_str)
        )
        self._image_links: dict[str, str] = {}


class LocalArtist(LocalCollectionFiltered[LocalTrack], Artist[LocalTrack]):
    """
    Object representing a collection of tracks by a single artist.

    :param tracks: A list of loaded tracks.
    :param name: The name of this artist.
        If given, the object only stores tracks that match the artist ``name`` given.
        If None, the list of tracks given are taken to be all the tracks by this artist.
    :param remote_wrangler: Optionally, provide a :py:class:`RemoteDataWrangler` object for processing URIs on tracks.
        If given, the wrangler can be used when calling __get_item__ to get an item from the collection from its URI.
    :raise LocalCollectionError: If the given tracks contain more than one unique value for
        ``artist`` when name is None.
    """

    __slots__ = ()
    __attributes_classes__ = (Artist, LocalCollection)

    @property
    def albums(self):
        return get_most_common_values(track.album for track in self.tracks if track.album)

    @property
    def genres(self) -> list[str]:
        """List of genres ordered by frequency of appearance on the tracks in this collection"""
        genres = (genre for track in self.tracks for genre in (track.genres if track.genres else []))
        return get_most_common_values(genres)

    @property
    def rating(self):
        """Average rating of all tracks by this artist"""
        ratings = tuple(track.rating for track in self.tracks if track.rating is not None)
        return sum(ratings) / len(ratings) if len(ratings) > 0 else None

    def __init__(
            self, tracks: Collection[LocalTrack], name: str | None = None, remote_wrangler: RemoteDataWrangler = None
    ):
        super().__init__(tracks=tracks, name=name, remote_wrangler=remote_wrangler)
        self.tracks.sort(
            key=lambda x: (x.album or _max_str,
                           x.disc_number or sys.maxsize,
                           x.track_number or sys.maxsize,
                           x.filename or _max_str)
        )


class LocalGenres(LocalCollectionFiltered[LocalTrack], Genre[LocalTrack]):
    """
    Object representing a collection of tracks within a genre.

    :param tracks: A list of loaded tracks.
    :param name: The name of this genre.
        If given, the object only stores tracks that match the genre ``name`` given.
        If None, the list of tracks given are taken to be all the tracks within this genre.
    :param remote_wrangler: Optionally, provide a :py:class:`RemoteDataWrangler` object for processing URIs on tracks.
        If given, the wrangler can be used when calling __get_item__ to get an item from the collection from its URI.
    :raise LocalCollectionError: If the given tracks contain more than one unique value for
        ``genre`` when name is None.
    """

    __slots__ = ()
    __attributes_classes__ = (Genre, LocalCollection)

    @property
    def albums(self):
        return get_most_common_values(track.album for track in self.tracks if track.album)

    @property
    def related_genres(self) -> list[str]:
        genres = (genre for track in self.tracks for genre in (track.genres if track.genres else []))
        return get_most_common_values(genres)

    def __init__(
            self, tracks: Collection[LocalTrack], name: str | None = None, remote_wrangler: RemoteDataWrangler = None
    ):
        super().__init__(tracks=tracks, name=name, remote_wrangler=remote_wrangler)
        self.tracks.sort(
            key=lambda x: (x.artist or _max_str,
                           x.album or _max_str,
                           x.disc_number or sys.maxsize,
                           x.track_number or sys.maxsize,
                           x.filename or _max_str)
        )
