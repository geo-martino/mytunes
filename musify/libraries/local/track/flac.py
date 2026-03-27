"""
The FLAC implementation of a :py:class:`LocalTrack`.
"""
from io import BytesIO
from typing import Any

import mutagen
import mutagen.flac
import mutagen.id3

from musify.field import TagMap
from musify.file.image import open_image, get_image_bytes
# noinspection PyProtectedMember
from musify.libraries.local.track._tags import TagReader, TagWriter
from musify.libraries.local.track.field import LocalTrackField
from musify.libraries.local.track.track import LocalTrack

try:
    from PIL import Image
except ImportError:
    Image = None


class _FLACTagReader(TagReader[mutagen.flac.FLAC]):

    __slots__ = ()

    def read_images(self):
        if Image is None:
            return

        values = self.file.pictures
        return [Image.open(BytesIO(value.data)) for value in values] if len(values) > 0 else None

    def check_for_images(self) -> bool:
        return len(self.file.pictures) > 0


class _FLACTagWriter(TagWriter[mutagen.flac.FLAC]):

    __slots__ = ()

    def _write_tag(self, tag_id: str | None, tag_value: Any, dry_run: bool = True) -> bool:
        if not dry_run:
            if isinstance(tag_value, (list, set, tuple)):
                self.file[tag_id] = list(map(str, tag_value))
            else:
                self.file[tag_id] = str(tag_value)
        return True

    def _write_images(self, track: LocalTrack, dry_run: bool = True) -> bool:
        updated = False
        for image_kind, image_link in track.image_links.items():
            image = open_image(image_link)
            image_kind_attr = image_kind.upper().replace(" ", "_")

            picture = mutagen.flac.Picture()
            picture.type = getattr(mutagen.id3.PictureType, image_kind_attr)
            picture.mime = Image.MIME[image.format]
            picture.data = get_image_bytes(image)

            if not dry_run:
                # clear all images, adding back those that don't match the new image's type
                pictures_current = self.file.pictures.copy()
                self.file.clear_pictures()
                for pic in pictures_current:
                    if pic.type != picture.type:
                        self.file.add_picture(pic)

                self.file.add_picture(picture)

            image.close()
            track.has_image = True
            updated = True

        return updated

    def _clear_tag(self, tag_name: str, dry_run: bool = True) -> bool:
        if tag_name == LocalTrackField.IMAGES.name.lower():
            self.file.clear_pictures()
            return True

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


class FLAC(LocalTrack[mutagen.flac.FLAC, _FLACTagReader, _FLACTagWriter]):

    __slots__ = ()

    valid_extensions = frozenset({".flac"})

    # noinspection SpellCheckingInspection
    #: Map of human-friendly tag name to ID3 tag ids for a given file type
    tag_map = TagMap(
        title=["title"],
        artist=["artist"],
        album=["album"],
        album_artist=["albumartist"],
        track_number=["tracknumber", "track"],
        track_total=["tracktotal"],
        genres=["genre"],
        date=["date", "year"],
        year=["year"],
        bpm=["bpm"],
        key=["initialkey"],
        disc_number=["discnumber"],
        disc_total=["disctotal"],
        compilation=["compilation"],
        comments=["comment", "description"],
    )

    def _create_reader(self, file: mutagen.flac.FLAC):
        return _FLACTagReader(file, tag_map=self.tag_map, remote_wrangler=self._remote_wrangler)

    def _create_writer(self, file: mutagen.flac.FLAC):
        return _FLACTagWriter(file, tag_map=self.tag_map, remote_wrangler=self._remote_wrangler)
