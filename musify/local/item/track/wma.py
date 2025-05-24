import struct
from collections.abc import Collection
from typing import Literal

import mutagen.asf
from mutagen.asf import ASFByteArrayAttribute
import mutagen.id3
from PIL import Image
from pydantic import Field, AliasChoices, PositiveFloat, InstanceOf, field_validator

from musify.local.item.album import LocalAlbum
from musify.local.item.artist import LocalArtist
from musify.local.item.genre import LocalGenre
from musify.local.item.track import LocalTrack
from musify.model.properties.date import SparseDate
from musify.model.properties.image import ImageLink, PICTURE_TYPES
from musify.model.properties.music import KeySignature
from musify.model.properties.order import Position


class WMA(LocalTrack[mutagen.asf.ASF]):
    format: Literal["wma"] = Field(
        description="The format (or file type) of the file.",
        validation_alias=AliasChoices("ext", "extension"),
        default=None,
        exclude=True,
    )

    name: str | None = Field(
        description="A title of this track.",
        default=None,
        validation_alias="Title"
    )
    artists: list[LocalArtist] | None = Field(
        description="The artists featured on this track.",
        default=None,
        validation_alias="Author"
    )
    album: LocalAlbum | None = Field(
        description="The album this track is featured on.",
        default=None,
        validation_alias="WM/AlbumTitle"
    )
    # album_artist: list[LocalAlbum] | None = Field(
    #     default=None,
    #     validation_alias="WM/AlbumArtist"
    # )
    genres: list[LocalGenre] | None = Field(
        description="The genres associated with this track.",
        default=None,
        validation_alias="WM/Genre"
    )
    track: Position | None = Field(
        description="The position of the track on the album that this track is featured on.",
        default=None,
        validation_alias=AliasChoices("WM/TrackNumber", "TotalTracks")
    )
    disc: Position | None = Field(
        description="The position of the disc in the album that this track is featured on.",
        default=None,
        validation_alias="WM/PartOfSet"
    )
    bpm: PositiveFloat | None = Field(
        description="The tempo of this track.",
        default=None,
        validation_alias="WM/BeatsPerMinute"
    )
    key: KeySignature | None = Field(
        description="The key of this track.",
        default=None,
        validation_alias="WM/InitialKey"
    )
    released_at: SparseDate | None = Field(
        description="The date this track was released.",
        default=None,
        validation_alias=AliasChoices("WM/Year", "WM/OriginalReleaseYear")
    )
    comments: list[str] = Field(
        description="Freeform comments that are associated with this track.",
        default_factory=list,
        validation_alias=AliasChoices("Description", "WM/Comments")
    )
    images: dict[str, InstanceOf[Image.Image] | ImageLink] | None = Field(
        description="Images associated with this track.",
        default=None,
        validation_alias="WM/Picture"
    )
    # compilation: list[str] | None = Field(
    #     default=None,
    #     validation_alias="COMPILATION"
    # )

    # noinspection PyNestedDecorators
    @field_validator(
        "name", "album", "track", "disc", "bpm", "key", "released_at", "uri",
        mode="before"
    )
    @classmethod
    def _deserialize_unicode_attribute[T](cls, value: T) -> T | str:
        # parent class validators always execute after child class validators
        # need to manually call required upstream parent validators here
        value = cls._extract_first_value_from_single_sequence(value)
        if not isinstance(value, mutagen.asf.ASFUnicodeAttribute):
            return value

        return value.value

    # noinspection PyNestedDecorators
    @field_validator(
        "artists", "genres", "comments",
        mode="before"
    )
    @classmethod
    def _deserialize_unicode_attributes[T](cls, value: T) -> T | list[str]:
        if not isinstance(value, tuple | list):
            return value
        return [cls._deserialize_unicode_attribute(v) for v in value]

    # noinspection PyNestedDecorators
    @field_validator("images", mode="before")
    @classmethod
    def _deserialize_images_from_wma_attributes[T](
            cls, attributes: T | bytes | ASFByteArrayAttribute | Collection[bytes | ASFByteArrayAttribute]
    ) -> T | dict[int, bytes]:
        if isinstance(attributes, bytes | ASFByteArrayAttribute):
            attributes = [attributes]

        if not isinstance(attributes, tuple | list):
            return attributes
        elif not all(isinstance(img, bytes | ASFByteArrayAttribute) for img in attributes):
            return attributes

        images: dict[int, T | bytes] = {}
        for attribute in attributes:
            if isinstance(attribute, ASFByteArrayAttribute):
                attribute = attribute.value

            id3_type, size = struct.unpack_from(b"<bi", attribute)

            if id3_type not in PICTURE_TYPES.values():  # first byte gives the id3 picture type in WMA-spec header
                # assume bytes don't contain WMA-spec header
                # assume bytes are raw image data for the cover front
                images[int(mutagen.id3.PictureType.COVER_FRONT)] = attribute
                continue

            # extract WMA-spec header information
            pos = 5
            mime = b""
            while attribute[pos:pos + 2] != b"\x00\x00":
                mime += attribute[pos:pos + 2]
                pos += 2

            pos += 2
            description = b""

            while attribute[pos:pos + 2] != b"\x00\x00":
                description += attribute[pos:pos + 2]
                pos += 2
            pos += 2

            images[id3_type] = attribute[pos:pos + size]

        return images
