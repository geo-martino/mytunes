import struct
from collections.abc import MutableMapping
from typing import Literal, ClassVar, Any

import mutagen.asf
import mutagen.id3
from PIL import Image, ImageFile as PILImageFile
from pydantic import Field, AliasChoices, PositiveFloat, field_validator, field_serializer, model_serializer
from pydantic_core.core_schema import SerializerFunctionWrapHandler, SerializationInfo, FieldSerializationInfo

from musify.local.item.album import LocalAlbum
from musify.local.item.artist import LocalArtist
from musify.local.item.genre import LocalGenre
from musify.local.item.track import LocalTrack
from musify.model.properties.date import SparseDate
from musify.model.properties.image import ImageURL, ImageFile
from musify.model.properties.music import KeySignature
from musify.model.properties.name import HasName
from musify.model.properties.order import Position


class WMA(LocalTrack[mutagen.asf.ASF]):
    format: Literal["wma"]

    class EmbeddedImage(LocalTrack.EmbeddedImage[mutagen.asf.ASF, mutagen.asf.ASFByteArrayAttribute]):
        alias: ClassVar[str] = "WM/Picture"

        @classmethod
        def _unpack_bytes(cls, attribute: bytes | mutagen.asf.ASFByteArrayAttribute) -> tuple[str | None, int] | None:
            if isinstance(attribute, mutagen.asf.ASFByteArrayAttribute):
                attribute = attribute.value

            id3_type, size = struct.unpack_from(b"<bi", attribute)
            try:  # first byte gives the id3 picture type in WMA-spec header
                id3_type = cls._get_type_from_number(id3_type)
            except ValueError:  # the given bytes do not contain WMA-spec header
                id3_type = None

            return id3_type, size

        @classmethod
        def _get_bytes(cls, attribute: Any) -> Any:
            if not isinstance(attribute, bytes | mutagen.asf.ASFByteArrayAttribute):
                return attribute
            if isinstance(attribute, mutagen.asf.ASFByteArrayAttribute):
                attribute = attribute.value

            id3_type, size = cls._unpack_bytes(attribute)
            if not id3_type:  # assume bytes are raw image data for the cover front
                return attribute

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

            return attribute[pos:pos + size]

        @classmethod
        def get_id3_type_from_tag(cls, attribute: bytes | mutagen.asf.ASFByteArrayAttribute) -> str | None:
            """Get the ID3 type from the given attribute."""
            id3_type, _ = cls._unpack_bytes(attribute)
            return id3_type

        def build(self, image: bytes | PILImageFile.ImageFile | None) -> mutagen.asf.ASFByteArrayAttribute | None:
            if image is None:
                return

            image, data = self._get_image_data(image)

            # noinspection PyTypeChecker
            header = struct.pack("<bi", int(self.id3_type), len(data))
            mime = Image.MIME[image.format].encode("utf-16")
            description = (self.description or "").encode("utf-16")

            data = b"\x00\x00".join((header + mime, description, data))
            return mutagen.asf.ASFByteArrayAttribute(data)

    name: str | None = Field(
        description="A title of this track.",
        default=None,
        alias="Title"
    )
    artists: list[LocalArtist] = Field(
        description="The artists featured on this track.",
        default_factory=list,
        alias="Author"
    )
    album: LocalAlbum | None = Field(
        description="The album this track is featured on.",
        default=None,
        alias="WM/AlbumTitle"
    )
    # album_artist: list[LocalAlbum] | None = Field(
    #     default=None,
    #     alias="WM/AlbumArtist"
    # )
    genres: list[LocalGenre] = Field(
        description="The genres associated with this track.",
        default_factory=list,
        alias="WM/Genre"
    )
    track: Position | None = Field(
        description="The position of the track on the album that this track is featured on.",
        default=None,
        validation_alias=AliasChoices("WM/TrackNumber", "TotalTracks"),
    )
    disc: Position | None = Field(
        description="The position of the disc in the album that this track is featured on.",
        default=None,
        alias="WM/PartOfSet"
    )
    bpm: PositiveFloat | None = Field(
        description="The tempo of this track.",
        default=None,
        alias="WM/BeatsPerMinute"
    )
    key: KeySignature | None = Field(
        description="The key of this track.",
        default=None,
        alias="WM/InitialKey"
    )
    released_at: SparseDate | None = Field(
        description="The date this track was released.",
        default=None,
        validation_alias=AliasChoices("WM/Year", "WM/OriginalReleaseYear"),
        serialization_alias="WM/Year",
    )
    comments: list[str] = Field(
        description="Freeform comments that are associated with this track.",
        default_factory=list,
        validation_alias=AliasChoices("WM/Comments", "Description"),
        serialization_alias="WM/Comments",
    )
    images: MutableMapping[str, ImageFile | ImageURL | EmbeddedImage] | None = Field(
        description="Images associated with this track.",
        default=None,
        alias=EmbeddedImage.alias,
    )
    # compilation: list[str] | None = Field(
    #     default=None,
    #     alias="COMPILATION"
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
        return list(map(cls._deserialize_unicode_attribute, value))

    # noinspection PyNestedDecorators
    @field_serializer(
        "name", "album", "disc", "bpm", "key", "released_at", "uri",
        mode="plain"
    )
    def _serialize_unicode_attribute[T](self, value: T) -> T | str:
        if not isinstance(value, tuple | list):
            value = [value]
        return mutagen.asf.ASFUnicodeAttribute(self._join_split_tags(value))

    # noinspection PyNestedDecorators
    @field_serializer(
        "artists", "genres", "comments",
        mode="plain"
    )
    def _serialize_unicode_attributes[T](self, value: T, info: FieldSerializationInfo) -> T | str:
        if not isinstance(value, tuple | list):
            value = [value]

        values = [v.name if isinstance(v, HasName) else v for v in value]
        self._extend_with_uris(values, info=info)
        return list(map(self._serialize_unicode_attribute, values))

    @field_serializer("track", mode="plain")
    def _serialize_position_tags(self, value: Position, info: FieldSerializationInfo) -> Any:
        return super()._serialize_position_tags(value, info=info)

    @model_serializer(mode="wrap")
    def _format_to_tags(self, handler: SerializerFunctionWrapHandler, info: SerializationInfo) -> dict[str, Any]:
        data = handler(self)
        if not info.by_alias or not isinstance(data, MutableMapping):  # not serializing to tag IDs
            return data

        self._flatten_dump(data)
        self._convert_values_to_list(data)
        return data
