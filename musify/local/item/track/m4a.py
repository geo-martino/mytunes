from collections.abc import MutableMapping
from typing import Literal, Any, ClassVar

import mutagen.id3
import mutagen.mp4
from PIL import ImageFile as PILImageFile
from pydantic import Field, AliasChoices, PositiveFloat, field_validator, field_serializer, model_serializer
from pydantic_core.core_schema import FieldSerializationInfo, SerializerFunctionWrapHandler, SerializationInfo

from musify.local.exception import FileError
from musify.local.item.album import LocalAlbum
from musify.local.item.artist import LocalArtist
from musify.local.item.genre import LocalGenre
from musify.local.item.track import LocalTrack
from musify.model.properties.date import SparseDate
from musify.model.properties.image import ImageURL, ImageFile
from musify.model.properties.music import KeySignature
from musify.model.properties.name import HasName
from musify.model.properties.order import Position


class M4A(LocalTrack[mutagen.mp4.MP4]):
    format: Literal["m4a"]

    class EmbeddedImage(LocalTrack.EmbeddedImage[mutagen.mp4.MP4, mutagen.mp4.MP4Cover]):
        alias: ClassVar[str] = "covr"

        @classmethod
        def _get_bytes(cls, value: Any) -> Any:
            return bytes(value) if isinstance(value, mutagen.mp4.MP4Cover) else value

        @classmethod
        def get_id3_type_from_tag(cls, value: mutagen.mp4.MP4Cover) -> str | None:
            # AFAIK, MP4 only supports a single image per track
            # Just return the value for COVER_FRONT type
            return cls._get_type_from_number(mutagen.id3.PictureType.COVER_FRONT)

        def build(self, image: bytes | PILImageFile.ImageFile | None) -> mutagen.mp4.MP4Cover | None:
            if image is None:
                return

            image, data = self._get_image_data(image)

            match image.format:
                case "PNG":
                    image_format = mutagen.mp4.AtomDataType.PNG
                case "JPEG" | "JPG":
                    image_format = mutagen.mp4.AtomDataType.JPEG
                case _:
                    name = self.__class__.__name__
                    raise FileError(f"Unrecognised image format for {name} cover image: {image.format}")

            return mutagen.mp4.MP4Cover(data, imageformat=image_format)

    name: str | None = Field(
        description="A title of this track.",
        default=None,
        alias="©nam"
    )
    artists: list[LocalArtist] | None = Field(
        description="The artists featured on this track.",
        default=None,
        alias="©ART"
    )
    album: LocalAlbum | None = Field(
        description="The album this track is featured on.",
        default=None,
        alias="©alb"
    )
    # album_artist: list[LocalAlbum] | None = Field(
    #     default=None,
    #     alias="aART"
    # )
    genres: list[LocalGenre] | None = Field(
        description="The genres associated with this track.",
        default=None,
        validation_alias=AliasChoices("©gen", "gnre", "----:com.apple.iTunes:GENRE"),
        serialization_alias="©gen",
    )
    track: Position | None = Field(
        description="The position of the track on the album that this track is featured on.",
        default=None,
        alias="trkn"
    )
    disc: Position | None = Field(
        description="The position of the disc in the album that this track is featured on.",
        default=None,
        alias="disk"
    )
    bpm: PositiveFloat | None = Field(
        description="The tempo of this track.",
        default=None,
        alias="tmpo"
    )
    key: KeySignature | None = Field(
        description="The key of this track.",
        default=None,
        alias="----:com.apple.iTunes:INITIALKEY"
    )
    released_at: SparseDate | None = Field(
        description="The date this track was released.",
        default=None,
        alias="©day"
    )
    comments: list[str] = Field(
        description="Freeform comments that are associated with this track.",
        default_factory=list,
        alias="©cmt"
    )
    images: MutableMapping[str, ImageFile | ImageURL | EmbeddedImage] | None = Field(
        description="Images associated with this track.",
        default=None,
        alias=EmbeddedImage.alias,
    )
    # compilation: list[str] | None = Field(
    #     default=None,
    #     alias="cpil"
    # )

    # noinspection PyNestedDecorators
    @field_validator("key", mode="before")
    @classmethod
    def _deserialize_free_form_field[T](cls, value: T) -> T | str:
        # parent class validators always execute after child class validators
        # need to manually call required upstream parent validators here
        value = cls._extract_first_value_from_sequence(value)
        if not isinstance(value, mutagen.mp4.MP4FreeForm):
            return value

        return value[:].decode()

    # noinspection PyNestedDecorators
    @field_validator("genres", mode="before")
    @classmethod
    def _deserialize_free_form_fields[T](cls, value: T) -> T | str:
        if not isinstance(value, tuple | list):
            return value
        return [cls._deserialize_free_form_field(v) for v in value]

    @model_serializer(mode="wrap")
    def _format_to_tags(self, handler: SerializerFunctionWrapHandler, info: SerializationInfo) -> dict[str, Any]:
        data = handler(self)
        if not info.by_alias or not isinstance(data, MutableMapping):  # not serializing to tag IDs
            return data

        self._convert_values_to_list(data)
        for key, val in data.items():
            if key.startswith("----:com.apple.iTunes:"):
                data[key] = [mutagen.mp4.MP4FreeForm(v.encode()) for v in val]
        return data

    @field_serializer(
        "album", "artists", "key", "released_at",
        mode="plain"
    )
    def _serialize_string(self, value: Any) -> str:
        if not isinstance(value, tuple | list):
            value = [value]

        value = self._join_split_tags(value)
        return value

    @field_serializer("genres", "comments", mode="plain")
    def _serialize_strings(self, value: Any, info: FieldSerializationInfo) -> list[str]:
        if not info.by_alias:  # not serializing to tag IDs
            return value

        values = [v.name if isinstance(v, HasName) else v for v in value]
        self._extend_with_uris(values, info=info)
        return list(map(str, values))

    @field_serializer("bpm", mode="plain")
    def _serialize_bpm(self, value: PositiveFloat, info: FieldSerializationInfo) -> Any:
        if not info.by_alias:  # not serializing to tag IDs
            return value
        return [int(value)]

    @field_serializer("track", "disc", mode="plain")
    def _serialize_position_tags(self, value: Position, info: FieldSerializationInfo) -> Any:
        if not info.by_alias:  # not serializing to tag IDs
            return value
        return [value.numbers]
