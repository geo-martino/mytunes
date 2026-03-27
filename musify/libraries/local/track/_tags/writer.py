"""
Implements all functionality pertaining to writing and deleting metadata/tags/properties for a :py:class:`LocalTrack`.
"""
from abc import ABCMeta, abstractmethod
from collections.abc import Mapping, Collection, Callable, MutableMapping
from dataclasses import dataclass
from typing import Any

import mutagen
from aiorequestful.types import UnitIterable

from musify.base import Result
from musify.libraries.core.object import Track
from musify.libraries.local.track._tags.base import TagProcessor
from musify.libraries.local.track.field import LocalTrackField as Tags
from musify.utils import to_collection


@dataclass(frozen=True)
class SyncResultTrack(Result):
    """Stores the results of a sync with local track"""
    #: Were changes to the file on the disk made.
    saved: bool
    #: Map of the tag updated and the index of the condition it satisfied to be updated.
    updated: MutableMapping[Tags, int]


class TagWriter[T: mutagen.FileType](TagProcessor, metaclass=ABCMeta):
    """Functionality for updating and removing tags/metadata/properties from a mutagen object."""

    __slots__ = ()

    #: The date format to use when saving string representations of dates to tag values
    date_format = "%Y-%m-%d"

    def delete_tags(self, tags: UnitIterable[Tags] = (), dry_run: bool = True) -> SyncResultTrack:
        """
        Remove tags from file.

        :param tags: Tags to remove.
        :param dry_run: Run function, but do not modify the file on the disk.
        :return: List of tags that have been removed.
        """
        if tags is None or (isinstance(tags, Collection) and len(tags) == 0):
            return SyncResultTrack(saved=False, updated={})

        tag_names = set(Tags.to_tags(tags))
        removed = set()
        for tag_name in tag_names:
            if self._clear_tag(tag_name, dry_run):
                removed.update(Tags.from_name(tag_name))

        save = not dry_run and len(removed) > 0
        if save:
            self.file.save()

        removed = sorted(removed, key=lambda x: Tags.all().index(x))
        return SyncResultTrack(saved=save, updated={u: 0 for u in removed})

    def _clear_tag(self, tag_name: str, dry_run: bool = True) -> bool:
        """
        Remove a tag by its tag name from the loaded file object in memory.

        :param tag_name: Tag name as found in :py:class:`TagMap` to remove.
        :param dry_run: Run function, but do not modify the loaded file in memory.
        :return: True if tag has been remove, False otherwise.
        """
        removed = False

        tag_ids = self.tag_map[tag_name]
        if tag_ids is None or len(tag_ids) is None:
            return removed

        for tag_id in tag_ids:
            if tag_id in self.file and self.file[tag_id]:
                if not dry_run:
                    del self.file[tag_id]
                removed = True

        return removed

    def clear_loaded_images(self) -> bool:
        """
        Clear the loaded embedded images for this track.
        Does not alter the actual file in any way, only the loaded object in memory.
        """
        tag_names = Tags.IMAGES.to_tag()
        removed = False
        for tag_name in tag_names:
            removed = removed or self._clear_tag(tag_name, dry_run=False)

        return removed

    def write(
            self,
            source: Track,
            target: Track,
            tags: UnitIterable[Tags] = Tags.ALL,
            replace: bool = False,
            dry_run: bool = True
    ):
        """
        Write the tags from the ``target`` track to the ``source`` track.
        Filter the tags written by supplying ``tags``.

        :param source: The source track i.e. the track object representing the currently saved file on the drive.
        :param target: The target track i.e. the track object containing new tags with which to update the file.
        :param tags: The tags to be updated.
        :param replace: Destructively overwrite the tag on the file if the ``source`` and ``target`` tags differ.
        :param dry_run: Run function, but do not modify the file on the disk.
        :return: The index number of the conditional that was met to warrant updating the file's tags.
            None if none of the conditions were met.
        """
        tags: set[Tags] = to_collection(tags, set)
        if Tags.ALL in tags:
            tags = set(Tags.all(only_tags=True))
        else:
            tags = {tag for tag in tags if tag in set(Tags.all(only_tags=True))}

        if any(f in tags for f in {Tags.TRACK, Tags.TRACK_NUMBER, Tags.TRACK_TOTAL}):
            tags -= {Tags.TRACK_NUMBER, Tags.TRACK_TOTAL}
            tags.add(Tags.TRACK)

        if any(f in tags for f in {Tags.DATE, Tags.YEAR, Tags.MONTH, Tags.DAY}):
            tags -= {Tags.YEAR, Tags.MONTH, Tags.DAY}
            tags.add(Tags.DATE)

        if any(f in tags for f in {Tags.DISC, Tags.DISC_NUMBER, Tags.DISC_TOTAL}):
            tags -= {Tags.DISC_NUMBER, Tags.DISC_TOTAL}
            tags.add(Tags.DISC)

        updated = {}
        for tag in tags:
            method: Callable[Any, Mapping[Tags, int] | int | None] = getattr(self, f"write_{tag.name.lower()}")
            result = method(source=source, target=target, replace=replace, dry_run=dry_run)
            if result is None:
                continue

            if isinstance(result, Mapping):
                updated |= result
            else:
                updated[tag] = result

        save = not dry_run and len(updated) > 0
        if save:
            self.file.save()

        return SyncResultTrack(saved=save, updated=updated)

    def write_tag(self, tag_id: str | None, tag_value: Any, dry_run: bool = True) -> bool | None:
        """
        Generic method for updating a tag value in the file.

        :param tag_id: ID of the tag for this file type.
        :param tag_value: New value to assign.
        :param dry_run: Run function, but do not modify the file on the disk.
        :return: The index number of the conditional that was met to warrant updating the file's tags.
            None if none of the conditions were met.
        """
        if tag_id is None:
            return False

        if tag_value is None:
            if not dry_run and tag_id in self.file and self.file[tag_id] is not None:
                del self.file[tag_id]
                return True
            return False

        return self._write_tag(tag_id=tag_id, tag_value=tag_value, dry_run=dry_run)

    @abstractmethod
    def _write_tag(self, tag_id: str | None, tag_value: Any, dry_run: bool = True) -> bool:
        """Implementation of tag writer specific to this file type."""
        raise NotImplementedError

    def write_title(self, source: Track, target: Track, replace: bool = False, dry_run: bool = True) -> int | None:
        """
        Write track title tags to file if appropriate related conditions are met.

        :param source: The source track i.e. the track object representing the currently saved file on the drive.
        :param target: The target track i.e. the track object containing new tags with which to update the file.
        :param replace: Destructively overwrite the tag on the file if the ``source`` and ``target`` tags differ.
        :param replace: Destructively overwrite the tag on the file if the ``source`` and ``target`` tags differ.
        :param dry_run: Run function, but do not modify the file on the disk.
        :return: The index number of the conditional that was met to warrant updating the file's tags.
            None if none of the conditions were met.
        """
        conditionals = [
            source.title is None and target.title is not None,
            replace and source.title != target.title
        ]
        if any(conditionals) and self._write_title(track=target, dry_run=dry_run):
            return next(i for i, c in enumerate(conditionals) if c)

    def _write_title(self, track: Track, dry_run: bool = True) -> bool:
        """
        Write the title tag from ``track`` to the stored file.

        :param track: The track with the tag to be written.
        :param dry_run: Run function, but do not modify the file on the disk.
        :return: True if the file has been updated or would have been written when ``dry_run`` is True.
        """
        return self.write_tag(next(iter(self.tag_map.title), None), track.title, dry_run)

    def write_artist(self, source: Track, target: Track, replace: bool = False, dry_run: bool = True) -> int | None:
        """
        Write the track artist tags to file if appropriate related conditions are met.

        :param source: The source track i.e. the track object representing the currently saved file on the drive.
        :param target: The target track i.e. the track object containing new tags with which to update the file.
        :param replace: Destructively overwrite the tag on the file if the ``source`` and ``target`` tags differ.
        :param dry_run: Run function, but do not modify the file on the disk.
        :return: The index number of the conditional that was met to warrant updating the file's tags.
            None if none of the conditions were met.
        """
        conditionals = [
            source.artist is None and target.artist is not None,
            replace and source.artist != target.artist
        ]
        if any(conditionals) and self._write_artist(track=target, dry_run=dry_run):
            return next(i for i, c in enumerate(conditionals) if c)

    def _write_artist(self, track: Track, dry_run: bool = True) -> bool:
        """
        Write the artist tag from ``track`` to the stored file.

        :param track: The track with the tag to be written.
        :param dry_run: Run function, but do not modify the file on the disk.
        :return: True if the file has been updated or would have been written when ``dry_run`` is True.
        """
        return self.write_tag(next(iter(self.tag_map.artist), None), track.artist, dry_run)

    def write_album(self, source: Track, target: Track, replace: bool = False, dry_run: bool = True) -> int | None:
        """
        Write the track album tags to file if appropriate related conditions are met.

        :param source: The source track i.e. the track object representing the currently saved file on the drive.
        :param target: The target track i.e. the track object containing new tags with which to update the file.
        :param replace: Destructively overwrite the tag on the file if the ``source`` and ``target`` tags differ.
        :param dry_run: Run function, but do not modify the file on the disk.
        :return: The index number of the conditional that was met to warrant updating the file's tags.
            None if none of the conditions were met.
        """
        conditionals = [
            source.album is None and target.album is not None,
            replace and source.album != target.album
        ]
        if any(conditionals) and self._write_album(track=target, dry_run=dry_run):
            return next(i for i, c in enumerate(conditionals) if c)

    def _write_album(self, track: Track, dry_run: bool = True) -> bool:
        """
        Write the album tag from ``track`` to the stored file.

        :param track: The track with the tag to be written.
        :param dry_run: Run function, but do not modify the file on the disk.
        :return: True if the file has been updated or would have been written when ``dry_run`` is True.
        """
        return self.write_tag(next(iter(self.tag_map.album), None), track.album, dry_run)

    def write_album_artist(
            self, source: Track, target: Track, replace: bool = False, dry_run: bool = True
    ) -> int | None:
        """
        Write the track album artist tags to file if appropriate related conditions are met.

        :param source: The source track i.e. the track object representing the currently saved file on the drive.
        :param target: The target track i.e. the track object containing new tags with which to update the file.
        :param replace: Destructively overwrite the tag on the file if the ``source`` and ``target`` tags differ.
        :param dry_run: Run function, but do not modify the file on the disk.
        :return: The index number of the conditional that was met to warrant updating the file's tags.
            None if none of the conditions were met.
        """
        conditionals = [
            source.album_artist is None and target.album_artist is not None,
            replace and source.album_artist != target.album_artist
        ]
        if any(conditionals) and self._write_album_artist(track=target, dry_run=dry_run):
            return next(i for i, c in enumerate(conditionals) if c)

    def _write_album_artist(self, track: Track, dry_run: bool = True) -> bool:
        """
        Write the album artist tag from ``track`` to the stored file.

        :param track: The track with the tag to be written.
        :param dry_run: Run function, but do not modify the file on the disk.
        :return: True if the file has been updated or would have been written when ``dry_run`` is True.
        """
        return self.write_tag(next(iter(self.tag_map.album_artist), None), track.album_artist, dry_run)

    def write_track(self, source: Track, target: Track, replace: bool = False, dry_run: bool = True) -> int | None:
        """
        Write the track number and track total tags to file if appropriate related conditions are met.

        :param source: The source track i.e. the track object representing the currently saved file on the drive.
        :param target: The target track i.e. the track object containing new tags with which to update the file.
        :param replace: Destructively overwrite the tag on the file if the ``source`` and ``target`` tags differ.
        :param dry_run: Run function, but do not modify the file on the disk.
        :return: The index number of the conditional that was met to warrant updating the file's tags.
            None if none of the conditions were met.
        """
        conditionals = [
            source.track_number is None and source.track_total is None and
            (target.track_number is not None or target.track_total is not None),
            replace and (source.track_number != target.track_number or source.track_total != target.track_total)
        ]
        if any(conditionals) and self._write_track(track=target, dry_run=dry_run):
            return next(i for i, c in enumerate(conditionals) if c)

    def _write_track(self, track: Track, dry_run: bool = True) -> bool:
        """
        Write the track number and track total tags from ``track`` to the stored file.

        :param track: The track with the tag to be written.
        :param dry_run: Run function, but do not modify the file on the disk.
        :return: True if the file has been updated or would have been written when ``dry_run`` is True.
        """
        tag_id_number = next(iter(self.tag_map.track_number), None)
        tag_id_total = next(iter(self.tag_map.track_total), None)

        zero_fill = len(str(track.track_total)) if track.track_total is not None else 1
        track_number = str(track.track_number).zfill(zero_fill)
        track_total = str(track.track_total) if track.track_total is not None else None

        if tag_id_number != tag_id_total and track_total is not None:
            number_updated = self.write_tag(tag_id_number, track_number, dry_run)
            total_updated = self.write_tag(tag_id_total, track_total, dry_run)
            return number_updated or total_updated
        elif track_total is not None:
            tag_value = self.num_sep.join([track_number, track_total])
        else:
            tag_value = track_number

        return self.write_tag(tag_id_number, tag_value, dry_run)

    def write_genres(self, source: Track, target: Track, replace: bool = False, dry_run: bool = True) -> int | None:
        """
        Write the track genre tags to file if appropriate related conditions are met.

        :param source: The source track i.e. the track object representing the currently saved file on the drive.
        :param target: The target track i.e. the track object containing new tags with which to update the file.
        :param replace: Destructively overwrite the tag on the file if the ``source`` and ``target`` tags differ.
        :param dry_run: Run function, but do not modify the file on the disk.
        :return: The index number of the conditional that was met to warrant updating the file's tags.
            None if none of the conditions were met.
        """
        conditionals = [source.genres is None and bool(target.genres), replace and source.genres != target.genres]
        if any(conditionals) and self._write_genres(track=target, dry_run=dry_run):
            return next(i for i, c in enumerate(conditionals) if c)

    def _write_genres(self, track: Track, dry_run: bool = True) -> bool:
        """
        Write the genre tags from ``track`` to the stored file.

        :param track: The track with the tag to be written.
        :param dry_run: Run function, but do not modify the file on the disk.
        :return: True if the file has been updated or would have been written when ``dry_run`` is True.
        """
        return self.write_tag(next(iter(self.tag_map.genres), None), track.genres, dry_run)

    def write_date(
            self, source: Track, target: Track, replace: bool = False, dry_run: bool = True
    ) -> dict[Tags, int] | None:
        """
        Write the track date and/or year/month/day tags to file if appropriate related conditions are met.

        :param source: The source track i.e. the track object representing the currently saved file on the drive.
        :param target: The target track i.e. the track object containing new tags with which to update the file.
        :param replace: Destructively overwrite the tag on the file if the ``source`` and ``target`` tags differ.
        :param dry_run: Run function, but do not modify the file on the disk.
        :return: The index number of the conditional that was met to warrant updating the file's tags.
            None if none of the conditions were met.
        """
        # date is just a composite of year + month + day, can safely ignore this in the conditionals
        values_exist = any({target.year is not None, target.month is not None, target.day is not None})
        conditionals = [
            source.year is None and source.month is None and source.day is None and values_exist,
            replace and (source.year != target.year or source.month != target.month or source.day != target.day)
        ]

        if not any(conditionals):
            return

        date, year, month, day = self._write_date(track=target, dry_run=dry_run)

        updated = {}
        condition = next(i for i, c in enumerate(conditionals) if c)
        if date:
            updated[Tags.DATE] = condition
        if year:
            updated[Tags.YEAR] = condition
        if month:
            updated[Tags.MONTH] = condition
        if day:
            updated[Tags.DAY] = condition

        return updated if updated else None

    def _write_date(self, track: Track, dry_run: bool = True) -> tuple[bool, bool, bool, bool]:
        """
        Write the date, year, month, and/or day tags from ``track`` to the stored file.

        :param track: The track with the tag to be written.
        :param dry_run: Run function, but do not modify the file on the disk.
        :return: True for each updated tag in the order (date, year, month, day)
            if the file has been updated or would have been written when ``dry_run`` is True.
        """
        date_str = track.date.strftime(self.date_format) if track.date else None
        if not date_str:
            date_str = f"{track.year}-{str(track.month).zfill(2)}" if track.month else str(track.year)
        date = self.write_tag(next(iter(self.tag_map.date), None), date_str, dry_run)
        if date:
            return True, False, False, False

        year = self.write_tag(next(iter(self.tag_map.year), None), track.year, dry_run)
        month = self.write_tag(next(iter(self.tag_map.month), None), track.month, dry_run)
        day = self.write_tag(next(iter(self.tag_map.day), None), track.day, dry_run)

        return date, year, month, day

    def write_bpm(self, source: Track, target: Track, replace: bool = False, dry_run: bool = True) -> int | None:
        """
        Write track bpm tags to file if appropriate related conditions are met.

        :param source: The source track i.e. the track object representing the currently saved file on the drive.
        :param target: The target track i.e. the track object containing new tags with which to update the file.
        :param replace: Destructively overwrite the tag on the file if the ``source`` and ``target`` tags differ.
        :param dry_run: Run function, but do not modify the file on the disk.
        :return: The index number of the conditional that was met to warrant updating the file's tags.
            None if none of the conditions were met.
        """
        source_bpm = int(source.bpm if source.bpm is not None else 0)
        target_bpm = int(target.bpm if target.bpm is not None else 0)

        conditionals = [
            source.bpm is None and target.bpm is not None and target_bpm > 30,
            source_bpm < 30 < target_bpm,
            replace and source_bpm != target_bpm
        ]

        if any(conditionals) and self._write_bpm(track=target, dry_run=dry_run):
            return next(i for i, c in enumerate(conditionals) if c)

    def _write_bpm(self, track: Track, dry_run: bool = True) -> bool:
        """
        Write the bpm tag from ``track`` to the stored file.

        :param track: The track with the tag to be written.
        :param dry_run: Run function, but do not modify the file on the disk.
        :return: True if the file has been updated or would have been written when ``dry_run`` is True.
        """
        return self.write_tag(next(iter(self.tag_map.bpm), None), track.bpm, dry_run)

    def write_key(self, source: Track, target: Track, replace: bool = False, dry_run: bool = True) -> int | None:
        """
        Write track key tags to file if appropriate related conditions are met.

        :param source: The source track i.e. the track object representing the currently saved file on the drive.
        :param target: The target track i.e. the track object containing new tags with which to update the file.
        :param replace: Destructively overwrite the tag on the file if the ``source`` and ``target`` tags differ.
        :param dry_run: Run function, but do not modify the file on the disk.
        :return: The index number of the conditional that was met to warrant updating the file's tags.
            None if none of the conditions were met.
        """
        conditionals = [source.key is None and target.key is not None, replace and source.key != target.key]

        if any(conditionals) and self._write_key(track=target, dry_run=dry_run):
            return next(i for i, c in enumerate(conditionals) if c)

    def _write_key(self, track: Track, dry_run: bool = True) -> bool:
        """
        Write the key tag from ``track`` to the stored file.

        :param track: The track with the tag to be written.
        :param dry_run: Run function, but do not modify the file on the disk.
        :return: True if the file has been updated or would have been written when ``dry_run`` is True.
        """
        return self.write_tag(next(iter(self.tag_map.key), None), track.key, dry_run)

    def write_disc(self, source: Track, target: Track, replace: bool = False, dry_run: bool = True) -> int | None:
        """
        Write track dic number and disc total tags to file if appropriate related conditions are met.

        :param source: The source track i.e. the track object representing the currently saved file on the drive.
        :param target: The target track i.e. the track object containing new tags with which to update the file.
        :param replace: Destructively overwrite the tag on the file if the ``source`` and ``target`` tags differ.
        :param dry_run: Run function, but do not modify the file on the disk.
        :return: The index number of the conditional that was met to warrant updating the file's tags.
            None if none of the conditions were met.
        """
        conditionals = [
            source.disc_number is None and source.disc_total is None and
            (target.disc_number is not None or target.disc_total is not None),
            replace and (source.disc_number != target.disc_number or source.disc_total != target.disc_total)
        ]
        if any(conditionals) and self._write_disc(track=target, dry_run=dry_run):
            return next(i for i, c in enumerate(conditionals) if c)

    def _write_disc(self, track: Track, dry_run: bool = True) -> bool:
        """
        Write the disc number and disc total tags from ``track`` to the stored file.

        :param track: The track with the tag to be written.
        :param dry_run: Run function, but do not modify the file on the disk.
        :return: True if the file has been updated or would have been written when ``dry_run`` is True.
        """
        tag_id_number = next(iter(self.tag_map.disc_number), None)
        tag_id_total = next(iter(self.tag_map.disc_total), None)

        zero_fill = len(str(track.disc_total)) if track.disc_total is not None else 1
        disc_number = str(track.disc_number).zfill(zero_fill)
        disc_total = str(track.disc_total) if track.disc_total is not None else None

        if tag_id_number != tag_id_total and disc_total is not None:
            number_updated = self.write_tag(tag_id_number, disc_number, dry_run)
            total_updated = self.write_tag(tag_id_total, disc_total, dry_run)
            return number_updated or total_updated
        elif disc_total is not None:
            tag_value = self.num_sep.join([disc_number, disc_total])
        else:
            tag_value = disc_number

        return self.write_tag(tag_id_number, tag_value, dry_run)

    def write_compilation(
            self, source: Track, target: Track, replace: bool = False, dry_run: bool = True
    ) -> int | None:
        """
        Write track compilation tags to file if appropriate related conditions are met.

        :param source: The source track i.e. the track object representing the currently saved file on the drive.
        :param target: The target track i.e. the track object containing new tags with which to update the file.
        :param replace: Destructively overwrite the tag on the file if the ``source`` and ``target`` tags differ.
        :param dry_run: Run function, but do not modify the file on the disk.
        :return: The index number of the conditional that was met to warrant updating the file's tags.
            None if none of the conditions were met.
        """
        conditionals = [
            source.compilation is None and target.compilation is not None,
            replace and source.compilation != target.compilation
        ]
        if any(conditionals) and self._write_compilation(track=target, dry_run=dry_run):
            return next(i for i, c in enumerate(conditionals) if c)

    def _write_compilation(self, track: Track, dry_run: bool = True) -> bool:
        """
        Write the compilation tag from ``track`` to the stored file.

        :param track: The track with the tag to be written.
        :param dry_run: Run function, but do not modify the file on the disk.
        :return: True if the file has been updated or would have been written when ``dry_run`` is True.
        """
        return self.write_tag(next(iter(self.tag_map.compilation), None), int(track.compilation), dry_run)

    def write_comments(self, source: Track, target: Track, replace: bool = False, dry_run: bool = True) -> int | None:
        """
        Write track comments tags to file if appropriate related conditions are met.

        :param source: The source track i.e. the track object representing the currently saved file on the drive.
        :param target: The target track i.e. the track object containing new tags with which to update the file.
        :param replace: Destructively overwrite the tag on the file if the ``source`` and ``target`` tags differ.
        :param dry_run: Run function, but do not modify the file on the disk.
        :return: The index number of the conditional that was met to warrant updating the file's tags.
            None if none of the conditions were met.
        """
        conditionals = [
            source.comments is None and bool(target.comments),
            replace and source.comments != target.comments
        ]
        if any(conditionals) and self._write_comments(track=target, dry_run=dry_run):
            return next(i for i, c in enumerate(conditionals) if c)

    def _write_comments(self, track: Track, dry_run: bool = True) -> bool:
        """
        Write the comments tags from ``track`` to the stored file.

        :param track: The track with the tag to be written.
        :param dry_run: Run function, but do not modify the file on the disk.
        :return: True if the file has been updated or would have been written when ``dry_run`` is True.
        """
        return self.write_tag(next(iter(self.tag_map.comments), None), track.comments, dry_run)

    # noinspection PyUnusedLocal
    def write_uri(self, source: Track, target: Track, replace: bool = False, dry_run: bool = True) -> int | None:
        """
        Write track URI tag to file if appropriate related conditions are met.

        :param source: The source track i.e. the track object representing the currently saved file on the drive.
        :param target: The target track i.e. the track object containing new tags with which to update the file.
        :param replace: Ignored.
        :param dry_run: Run function, but do not modify the file on the disk.
        :return: The index number of the conditional that was met to warrant updating the file's tags.
            None if none of the conditions were met.
        """
        if not self.remote_wrangler:
            return

        conditionals = [source.uri != target.uri or source.has_uri != target.has_uri]

        if any(conditionals) and self._write_uri(track=target, dry_run=dry_run):
            return next(i for i, c in enumerate(conditionals) if c)

    def _write_uri(self, track: Track, dry_run: bool = True) -> bool:
        """
        Write the URI tag from ``track`` to the stored file.

        :param track: The track with the tag to be written.
        :param dry_run: Run function, but do not modify the file on the disk.
        :return: True if the file has been updated or would have been written when ``dry_run`` is True.
        """
        tag_id = next(iter(self.tag_map[self.uri_tag.name.lower()]), None)
        tag_value = self.remote_wrangler.unavailable_uri_dummy if not track.has_uri else track.uri
        return self.write_tag(tag_id, tag_value, dry_run)

    def write_images(self, source: Track, target: Track, replace: bool = False, dry_run: bool = True) -> int | None:
        """
        Write images to file if appropriate related conditions are met.

        :param source: The source track i.e. the track object representing the currently saved file on the drive.
        :param target: The target track i.e. the track object containing new tags with which to update the file.
        :param replace: Destructively overwrite the tag on the file if the ``source`` and ``target`` tags differ.
        :param dry_run: Run function, but do not modify the file on the disk.
        :return: The index number of the conditional that was met to warrant updating the file's tags.
            None if none of the conditions were met.
        """
        conditionals = [source.has_image is False and bool(target.image_links), replace and bool(target.image_links)]

        if any(conditionals) and self._write_images(track=target, dry_run=dry_run):
            return next(i for i, c in enumerate(conditionals) if c)

    @abstractmethod
    def _write_images(self, track: Track, dry_run: bool = True) -> bool:
        """
        Write the images from the ``image_links`` in ``track`` to the stored file.

        :param track: The track with the tag to be written.
        :param dry_run: Run function, but do not modify the file on the disk.
        :return: True if the file has been updated or would have been written when ``dry_run`` is True.
        """
        raise NotImplementedError
