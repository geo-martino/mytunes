"""
Implements all functionality pertaining to reading metadata/tags/properties for a :py:class:`LocalTrack`.
"""
import re
from abc import ABCMeta, abstractmethod
from collections.abc import Iterable
from typing import Any

import mutagen

from musify.libraries.local.track._tags.base import TagProcessor
from musify.libraries.remote.core.types import RemoteIDType
from musify.utils import to_collection

try:
    from PIL import Image
    ImageType = list[Image.Image] | None
except ImportError:
    Image = None
    ImageType = None


class TagReader[T: mutagen.FileType](TagProcessor, metaclass=ABCMeta):
    """Functionality for reading tags/metadata/properties from a mutagen object."""

    __slots__ = ()

    def read_tag(self, tag_ids: Iterable[str]) -> list[Any] | None:
        """Extract all tag values from file for a given list of tag IDs"""
        values = []
        for tag_id in tag_ids:
            value = self.file.get(tag_id)
            if value is None or (isinstance(value, str) and len(value.strip()) == 0):
                # skip null or empty/blank strings
                continue

            if isinstance(value, (list, set, tuple)) and all(isinstance(val, str) for val in value):
                values.extend(v for val in value for v in val.split('\x00'))
            elif isinstance(value, (list, set, tuple)):
                values.extend(value)
            elif isinstance(value, str):
                values.extend(value.split('\x00'))
            else:
                values.append(value)

        return values if len(values) > 0 else None

    def read_title(self) -> str | None:
        """Extract track title tags from file"""
        values = self.read_tag(self.tag_map.title)
        return str(values[0]) if values is not None else None

    def read_artist(self) -> str | None:
        """Extract artist tags from file"""
        values = self.read_tag(self.tag_map.artist)
        return str(values[0]) if values is not None else None

    def read_album(self) -> str | None:
        """Extract album tags from file"""
        values = self.read_tag(self.tag_map.album)
        return str(values[0]) if values is not None else None

    def read_album_artist(self) -> str | None:
        """Extract album artist tags from file"""
        values = self.read_tag(self.tag_map.album_artist)
        return str(values[0]) if values is not None else None

    def read_track_number(self) -> int | None:
        """Extract track number tags from file"""
        values = self.read_tag(self.tag_map.track_number)
        if values is None:
            return

        value = str(values[0])
        return int(value.split(self.num_sep)[0]) if self.num_sep in value else int(value)

    def read_track_total(self) -> int | None:
        """Extract total track count tags from file"""
        values = self.read_tag(self.tag_map.track_total)
        if values is None:
            return

        value = str(values[0])
        return int(value.split(self.num_sep)[1]) if self.num_sep in value else int(value)

    def read_genres(self) -> list[str] | None:
        """Extract genre tags from file"""
        values = self.read_tag(self.tag_map.genres)
        return list(map(str, values)) if values is not None else None

    def read_date(self) -> tuple[int | None, int | None, int | None] | None:
        """Extract year tags from file"""
        values = self.read_tag(self.tag_map.date)

        if values is None:  # attempt to read each part individually
            year = self.read_tag(self.tag_map.year)
            year = int(re.match(r"(\d{4})", str(year[0])).group(1)) if year else None
            month = self.read_tag(self.tag_map.month)
            month = int(re.match(r"(\d{1,2})", str(month[0])).group(1)) if month else None
            day = self.read_tag(self.tag_map.day)
            day = int(re.match(r"(\d{1,2})", str(day[0])).group(1)) if day else None
            return year, month, day
        elif 0 < len(values) <= 3 and all(str(value).isdigit() for value in values):
            values = ["/".join(values)]  # just join to string and allow later regex matches to determine format

        # YYYY-MM-DD
        match = re.match(r"(\d{4})\D+(\d{1,2})\D+(\d{1,2})", str(values[0]))
        if match:
            return int(match.group(1)), int(match.group(2)), int(match.group(3))

        # DD-MM-YY
        match = re.match(r"(\d{1,2})\D+(\d{1,2})\D+(\d{4})", str(values[0]))
        if match:
            return int(match.group(3)), int(match.group(2)), int(match.group(1))

        # YYYY-MM
        match = re.match(r"(\d{4})\D+(\d{1,2})", str(values[0]))
        if match:
            return int(match.group(1)), int(match.group(2)), None

        # MM-YYYY
        match = re.match(r"(\d{4})\D+(\d{1,2})", str(values[0]))
        if match:
            return int(match.group(2)), int(match.group(1)), None

        # YYYY
        match = re.match(r"(\d{4})", str(values[0]))
        if match:
            return int(match.group(1)), None, None

    def read_bpm(self) -> float | None:
        """Extract BPM tags from file"""
        values = self.read_tag(self.tag_map.bpm)
        try:
            return float(values[0]) if values is not None else None
        except ValueError:
            return None

    def read_key(self) -> str | None:
        """Extract key tags from file"""
        values = self.read_tag(self.tag_map.key)
        return str(values[0]) if values is not None else None

    def read_disc_number(self) -> int | None:
        """Extract disc number tags from file"""
        values = self.read_tag(self.tag_map.disc_number)
        if values is None:
            return

        value = str(values[0])
        return int(value.split(self.num_sep)[0]) if self.num_sep in value else int(value)

    def read_disc_total(self) -> int | None:
        """Extract total disc count tags from file"""
        values = self.read_tag(self.tag_map.disc_total)
        if values is None:
            return

        value = str(values[0])
        return int(value.split(self.num_sep)[1]) if self.num_sep in value else int(value)

    def read_compilation(self) -> bool | None:
        """Extract compilation tags from file"""
        values = self.read_tag(self.tag_map.compilation)
        try:
            return bool(int(values[0])) if values is not None else None
        except ValueError:
            return None

    def read_comments(self) -> list[str] | None:
        """Extract comment tags from file"""
        values = self.read_tag(self.tag_map.comments)
        return set(map(str, values)) if values is not None else None

    def read_uri(self) -> str | None:
        """Extract data relating to remote URI value from file"""
        wrangler = self.remote_wrangler
        if not wrangler:
            return

        read_method = getattr(self, f"read_{self.uri_tag.name.lower()}")
        possible_values: tuple[str, ...] | None = to_collection(read_method())
        if not possible_values:
            return None

        # WORKAROUND: for dodgy MP3 tag comments; split on null and take first value
        possible_values = tuple(val for values in possible_values for val in values.split("\x00"))
        for uri in possible_values:
            if uri == wrangler.unavailable_uri_dummy or wrangler.validate_id_type(uri, kind=RemoteIDType.URI):
                return uri

        return None

    @abstractmethod
    def read_images(self) -> ImageType:
        """Extract image from file"""
        raise NotImplementedError

    def check_for_images(self) -> bool:
        """Check if file has embedded images"""
        return self.read_tag(self.tag_map.images) is not None
