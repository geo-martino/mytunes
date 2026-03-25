import struct
from collections.abc import MutableMapping, Iterable
from typing import ClassVar, Any, final, Annotated

import mutagen.asf
import mutagen.id3
from PIL import Image, ImageFile as PILImageFile
from pydantic import Field, AliasChoices, PositiveFloat, field_validator, field_serializer, model_serializer, \
    InstanceOf, computed_field
from pydantic_core.core_schema import SerializerFunctionWrapHandler, SerializationInfo, FieldSerializationInfo

from musify._types import StrippedString
from musify.local.item.album import LocalAlbum
from musify.local.item.artist import LocalArtist
from musify.local.item.genre import LocalGenre
from musify.local.item.track import LocalTrack
from musify.models.metadata import TagAttribute
from musify.models.properties.date import SparseDate
from musify.models.properties.image import ImageURL, ImageFile
from musify.models.properties.music import KeySignature
from musify.models.properties.name import HasName
from musify.models.properties.order import Position


@final
class WMA(LocalTrack[mutagen.asf.ASF]):
    __final__ = True
    __supported_extensions__ = frozenset({"wma"})

    class EmbeddedImage(LocalTrack.EmbeddedImage[mutagen.asf.ASFByteArrayAttribute]):
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

    name: Annotated[StrippedString | None, TagAttribute()] = Field(
        description="A title of this track.",
        default=None,
        alias="Title"
    )
    artists: Annotated[list[LocalArtist], TagAttribute(), TagAttribute("artist")] = Field(
        description="The artists featured on this track.",
        default_factory=list,
        alias="Author"
    )
    album: Annotated[LocalAlbum | None, TagAttribute()] = Field(
        description="The album this track is featured on.",
        default=None,
        alias="WM/AlbumTitle"
    )
    genres: Annotated[list[LocalGenre], TagAttribute(), TagAttribute("genre")] = Field(
        description="The genres associated with this track.",
        default_factory=list,
        alias="WM/Genre"
    )
    track: Annotated[Position | None, TagAttribute()] = Field(
        description="The position of the track on the album that this track is featured on.",
        default=None,
        validation_alias=AliasChoices("WM/TrackNumber", "TotalTracks"),
    )
    disc: Annotated[Position | None, TagAttribute()] = Field(
        description="The position of the disc in the album that this track is featured on.",
        default=None,
        alias="WM/PartOfSet"
    )
    bpm: Annotated[PositiveFloat | None, TagAttribute()] = Field(
        description="The tempo of this track.",
        default=None,
        alias="WM/BeatsPerMinute"
    )
    key: Annotated[KeySignature | None, TagAttribute()] = Field(
        description="The key of this track.",
        default=None,
        alias="WM/InitialKey"
    )
    released_at: Annotated[SparseDate | None, TagAttribute()] = Field(
        description="The date this track was released.",
        default=None,
        validation_alias=AliasChoices("WM/Year", "WM/OriginalReleaseYear"),
        serialization_alias="WM/Year",
    )
    comments: Annotated[list[str], TagAttribute()] = Field(
        description="Freeform comments that are associated with this track.",
        default_factory=list,
        validation_alias=AliasChoices("WM/Comments", "Description"),
        serialization_alias="WM/Comments",
    )
    images: Annotated[MutableMapping[str, ImageFile | ImageURL | EmbeddedImage] | None, TagAttribute()] = Field(
        description="Images associated with this track.",
        default=None,
        alias=EmbeddedImage.alias,
    )

    @computed_field(
        description="The main artist on the album.",
        alias="WM/AlbumArtist",
    )
    def album_artist(self) -> Annotated[LocalArtist | None, TagAttribute()]:
        return super().album_artist

    @album_artist.setter
    def album_artist(self, value: LocalArtist) -> None:
        value = self._deserialize_unicode_attribute(value)
        super(type(self), type(self)).album_artist.fset(self, value)

    @computed_field(
        description="Whether the album is a compilation album.",
        alias="COMPILATION",
    )
    def compilation(self) -> Annotated[bool | None, TagAttribute()]:
        return super().compilation

    @compilation.setter
    def compilation(self, value: bool | None) -> None:
        value = self._deserialize_unicode_attribute(value)
        super(type(self), type(self)).compilation.fset(self, value)

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

    @field_serializer("compilation", mode="plain", when_used="unless-none")
    def _serialize_bool[T: bool](self, value: T, info: FieldSerializationInfo) -> str:
        if not info.by_alias and info.mode != "json":
            return value
        return self._serialize_unicode_attribute(str(int(value)), info=info)

    @field_serializer("album", "album_artist", mode="plain", when_used="unless-none")
    def _serialize_name(
        self, value: str | HasName, info: SerializationInfo
    ) -> str | InstanceOf[mutagen.asf.ASFUnicodeAttribute]:
        if info.mode == "json":
            return self._extract_name(value)
        # noinspection PyArgumentList
        return self._serialize_unicode_attribute(value, info=info)

    @field_serializer("artists", "genres", mode="plain", when_used="unless-none")
    def _serialize_names(
        self, value: Iterable[str | HasName], info: SerializationInfo
    ) -> list[str] | InstanceOf[mutagen.asf.ASFUnicodeAttribute]:
        if info.mode == "json":
            return self._extract_names(value)
        # noinspection PyArgumentList
        return self._serialize_unicode_attributes(value, info=info)

    # noinspection PyNestedDecorators
    @field_serializer(
        "name", "disc", "bpm", "key", "released_at", "uri",
        mode="plain", when_used="unless-none",
    )
    def _serialize_unicode_attribute[T: str | HasName](
        self, value: T, info: SerializationInfo
    ) -> T | InstanceOf[mutagen.asf.ASFUnicodeAttribute]:
        if not info.by_alias or info.mode == "json":
            return value
        if not isinstance(value, tuple | list):
            value = [value]

        value = self._join_split_tags(value)
        return mutagen.asf.ASFUnicodeAttribute(value)

    # noinspection PyNestedDecorators
    @field_serializer("comments", mode="plain", when_used="unless-none")
    def _serialize_unicode_attributes[T](self, value: T, info: FieldSerializationInfo) -> T | str:
        if not isinstance(value, tuple | list):
            value = [value]

        values = self._extract_names(value)
        self._extend_with_uris(values, info=info)
        # noinspection PyArgumentList
        return [self._serialize_unicode_attribute(val, info=info) for val in values]

    @field_serializer("track", mode="plain", when_used="unless-none")
    def _serialize_position_tags(self, value: Position, info: FieldSerializationInfo) -> str | dict[str, str] | None:
        tags = super()._serialize_position_tags(value, info=info)
        return {k: self._serialize_unicode_attribute(v, info=info) for k, v in tags.items()} if tags else None

    @model_serializer(mode="wrap")
    def _format_to_tags(self, handler: SerializerFunctionWrapHandler, info: SerializationInfo) -> dict[str, Any]:
        data = handler(self)
        if not info.by_alias or not isinstance(data, dict):  # not serializing to tag IDs
            return data

        self._flatten_dump(data)
        self._convert_values_to_list(data)
        return data
