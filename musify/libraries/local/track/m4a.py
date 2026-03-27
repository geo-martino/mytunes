"""
The M4A implementation of a :py:class:`LocalTrack`.
"""
from collections.abc import Iterable
from io import BytesIO
from typing import Any

import mutagen
import mutagen.mp4

from musify.field import TagMap
from musify.file.image import open_image, get_image_bytes
# noinspection PyProtectedMember
from musify.libraries.local.track._tags import TagReader, TagWriter
from musify.libraries.local.track.track import LocalTrack
from musify.utils import to_collection

try:
    from PIL import Image
except ImportError:
    Image = None


class _M4ATagReader(TagReader[mutagen.mp4.MP4]):

    __slots__ = ()

    def read_tag(self, tag_ids: Iterable[str]) -> list[Any] | None:
        """Extract all tag values for a given list of tag IDs"""
        values = []
        for tag_id in tag_ids:
            value = self.file.get(tag_id)
            if value is None or (isinstance(value, str) and len(value.strip()) == 0):
                # skip null or empty/blank strings
                continue

            if tag_id.startswith("----:com.apple.iTunes") and isinstance(value, (list, set, tuple)):
                value = [v for val in value for v in val.decode("utf-8").split('\x00')]
            elif isinstance(value, bytes):
                value = value.decode("utf-8").split('\x00')

            values.extend(value) if isinstance(value, (list, set, tuple)) else values.append(value)

        return values if len(values) > 0 else None

    def read_track_number(self) -> int | None:
        values = self.read_tag(self.tag_map.track_number)
        return int(values[0][0]) if values is not None else None

    def read_track_total(self) -> int | None:
        values = self.read_tag(self.tag_map.track_total)
        return int(values[0][1]) if values is not None else None

    def read_key(self) -> str | None:
        values = self.read_tag(self.tag_map.key)
        return str(values[0][:]) if values is not None else None

    def read_disc_number(self) -> int | None:
        values = self.read_tag(self.tag_map.disc_number)
        return int(values[0][0]) if values is not None else None

    def read_disc_total(self) -> int | None:
        values = self.read_tag(self.tag_map.disc_total)
        return int(values[0][1]) if values is not None else None

    def read_images(self):
        if Image is None:
            return

        values = self.read_tag(self.tag_map.images)
        return [Image.open(BytesIO(bytes(value))) for value in values] if values is not None else None


class _M4ATagWriter(TagWriter[mutagen.mp4.MP4]):

    __slots__ = ()

    def _write_tag(self, tag_id: str | None, tag_value: Any, dry_run: bool = True) -> bool:
        if not dry_run:
            if tag_id.startswith("----:com.apple.iTunes"):
                self.file[tag_id] = [
                    mutagen.mp4.MP4FreeForm(str(v).encode("utf-8"), 1) for v in to_collection(tag_value)
                ]
            elif isinstance(tag_value, bool):
                self.file[tag_id] = tag_value
            elif isinstance(tag_value, tuple):
                self.file[tag_id] = [tag_value]
            else:
                self.file[tag_id] = to_collection(tag_value, list)
        return True

    def _write_track(self, track: LocalTrack, dry_run: bool = True) -> bool:
        tag_id = next(iter(self.tag_map.track_number), None)
        tag_value = (track.track_number, track.track_total)
        return self.write_tag(tag_id, tag_value, dry_run)

    def _write_date(self, track: LocalTrack, dry_run: bool = True) -> tuple[bool, bool, bool, bool]:
        date_str = track.date.strftime(self.date_format) if track.date else None
        if not date_str:
            date_str = f"{track.year}-{str(track.month).zfill(2)}" if track.month else str(track.year)
        date = self.write_tag(next(iter(self.tag_map.date), None), date_str, dry_run)
        if date:
            return date, False, False, False

        year = self.write_tag(next(iter(self.tag_map.year), None), str(track.year) if track.year else None, dry_run)
        month = self.write_tag(next(iter(self.tag_map.month), None), str(track.month) if track.month else None, dry_run)
        day = self.write_tag(next(iter(self.tag_map.day), None), str(track.day) if track.day else None, dry_run)

        return date, year, month, day

    def _write_bpm(self, track: LocalTrack, dry_run: bool = True) -> bool:
        bpm = int(track.bpm) if track.bpm is not None else None
        return self.write_tag(next(iter(self.tag_map.bpm), None), bpm, dry_run)

    def _write_disc(self, track: LocalTrack, dry_run: bool = True) -> bool:
        tag_id = next(iter(self.tag_map.disc_number), None)
        tag_value = (track.disc_number, track.disc_total)
        return self.write_tag(tag_id, tag_value, dry_run)

    def _write_compilation(self, track: LocalTrack, dry_run: bool = True) -> bool:
        return self.write_tag(next(iter(self.tag_map.compilation), None), track.compilation, dry_run)

    def _write_images(self, track: LocalTrack, dry_run: bool = True) -> bool:
        tag_id = next(iter(self.tag_map.images), None)

        updated = False
        tag_value = []
        for image_link in track.image_links.values():
            image = open_image(image_link)

            if image.format == "PNG":
                image_format = mutagen.mp4.MP4Cover.FORMAT_PNG
            else:
                image_format = mutagen.mp4.MP4Cover.FORMAT_JPEG

            tag_value.append(mutagen.mp4.MP4Cover(get_image_bytes(image), imageformat=image_format))
            image.close()

        if len(tag_value) > 0:
            updated = self.write_tag(tag_id, tag_value, dry_run)

        track.has_image = updated or track.has_image
        return updated


class M4A(LocalTrack[mutagen.mp4.MP4, _M4ATagReader, _M4ATagWriter]):

    __slots__ = ()

    valid_extensions = frozenset({".m4a"})

    # noinspection SpellCheckingInspection
    #: Map of human-friendly tag name to ID3 tag ids for a given file type
    tag_map = TagMap(
        title=["©nam"],
        artist=["©ART"],
        album=["©alb"],
        album_artist=["aART"],
        track_number=["trkn"],
        track_total=["trkn"],
        genres=["----:com.apple.iTunes:GENRE", "©gen", "gnre"],
        date=["©day"],
        bpm=["tmpo"],
        key=["----:com.apple.iTunes:INITIALKEY"],
        disc_number=["disk"],
        disc_total=["disk"],
        compilation=["cpil"],
        comments=["©cmt"],
        images=["covr"],
    )

    def _create_reader(self, file: mutagen.mp4.MP4):
        return _M4ATagReader(file, tag_map=self.tag_map, remote_wrangler=self._remote_wrangler)

    def _create_writer(self, file: mutagen.mp4.MP4):
        return _M4ATagWriter(file, tag_map=self.tag_map, remote_wrangler=self._remote_wrangler)
