"""
The WMA implementation of a :py:class:`LocalTrack`.
"""
import struct
from collections.abc import Collection, Iterable
from io import BytesIO
from typing import Any

import mutagen
import mutagen.asf
import mutagen.id3

from musify.field import TagMap
from musify.file.image import open_image, get_image_bytes
# noinspection PyProtectedMember
from musify.libraries.local.track._tags import TagReader, TagWriter
from musify.libraries.local.track.track import LocalTrack

try:
    from PIL import Image, UnidentifiedImageError
except ImportError:
    Image = None
    UnidentifiedImageError = None


class _WMATagReader(TagReader[mutagen.asf.ASF]):

    __slots__ = ()

    def read_tag(self, tag_ids: Iterable[str]) -> list[Any] | None:
        # WMA tag values are returned as mutagen.asf._attrs.ASFUnicodeAttribute
        values = []
        for tag_id in tag_ids:
            value: Collection[mutagen.asf.ASFBaseAttribute] = self.file.get(tag_id)
            if value is None:
                # skip null or empty/blank strings
                continue

            values.extend([v.value for v in value if not (isinstance(value, str) and len(value.strip()) == 0)])

        return values if len(values) > 0 else None

    def read_images(self):
        if Image is None:
            return

        values = self.read_tag(self.tag_map.images)
        if values is None:
            return

        images: list[Image.Image] = []
        for i, value in enumerate(values):
            try:
                # first attempt to open image from bytes; assumes bytes value refer only to the image data
                images.append(Image.open(BytesIO(value)))
                continue
            except UnidentifiedImageError:
                # the bytes are encoded per WMA spec
                # bytes need to be analysed first to extract the bytes that refer to the image data
                pass

            v_type, v_size = struct.unpack_from(b"<bi", value)

            pos = 5
            mime = b""
            while value[pos:pos + 2] != b"\x00\x00":
                mime += value[pos:pos + 2]
                pos += 2

            pos += 2
            description = b""

            while value[pos:pos + 2] != b"\x00\x00":
                description += value[pos:pos + 2]
                pos += 2
            pos += 2

            image_data: bytes = value[pos:pos + v_size]
            images.append(Image.open(BytesIO(image_data)))

        return images


class _WMATagWriter(TagWriter[mutagen.asf.ASF]):

    __slots__ = ()

    def _write_tag(self, tag_id: str | None, tag_value: Any, dry_run: bool = True) -> bool:
        if not dry_run:
            if isinstance(tag_value, (list, set, tuple)):
                if all(isinstance(v, mutagen.asf.ASFByteArrayAttribute) for v in tag_value):
                    self.file[tag_id] = tag_value
                else:
                    self.file[tag_id] = [mutagen.asf.ASFUnicodeAttribute(str(v)) for v in tag_value]
            else:
                self.file[tag_id] = mutagen.asf.ASFUnicodeAttribute(str(tag_value))
        return True

    def _write_images(self, track: LocalTrack, dry_run: bool = True) -> bool:
        tag_id = next(iter(self.tag_map.images), None)

        updated = False
        tag_value = []
        for image_kind, image_link in track.image_links.items():
            image_kind_attr = image_kind.upper().replace(" ", "_")
            image_type: mutagen.id3.PictureType = getattr(mutagen.id3.PictureType, image_kind_attr)

            image = open_image(image_link)
            data = get_image_bytes(image)
            tag_data = struct.pack("<bi", image_type, len(data))
            tag_data += Image.MIME[image.format].encode("utf-16") + b"\x00\x00"  # mime
            tag_data += "".encode("utf-16") + b"\x00\x00"  # description
            tag_data += data

            tag_value.append(mutagen.asf.ASFByteArrayAttribute(tag_data))
            image.close()

        if len(tag_value) > 0:
            updated = self.write_tag(tag_id, tag_value, dry_run)

        track.has_image = updated or track.has_image
        return updated


class WMA(LocalTrack[mutagen.asf.ASF, _WMATagReader, _WMATagWriter]):

    __slots__ = ()

    valid_extensions = frozenset({".wma"})

    #: Map of human-friendly tag name to ID3 tag ids for a given file type
    tag_map = TagMap(
        title=["Title"],
        artist=["Author"],
        album=["WM/AlbumTitle"],
        album_artist=["WM/AlbumArtist"],
        track_number=["WM/TrackNumber"],
        track_total=["TotalTracks", "WM/TrackNumber"],
        genres=["WM/Genre"],
        year=["WM/Year", "WM/OriginalReleaseYear"],
        bpm=["WM/BeatsPerMinute"],
        key=["WM/InitialKey"],
        disc_number=["WM/PartOfSet"],
        disc_total=["WM/PartOfSet"],
        compilation=["COMPILATION"],
        comments=["Description", "WM/Comments"],
        images=["WM/Picture"],
    )

    def _create_reader(self, file: mutagen.asf.ASF):
        return _WMATagReader(file, tag_map=self.tag_map, remote_wrangler=self._remote_wrangler)

    def _create_writer(self, file: mutagen.asf.ASF):
        return _WMATagWriter(file, tag_map=self.tag_map, remote_wrangler=self._remote_wrangler)
