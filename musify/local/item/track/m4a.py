from collections.abc import MutableMapping, Iterable
from typing import Any, ClassVar, final, Annotated

import mutagen.id3
import mutagen.mp4
from PIL import ImageFile as PILImageFile
from pydantic import Field, AliasChoices, PositiveFloat, field_validator, field_serializer, model_serializer, \
    computed_field
from pydantic_core.core_schema import FieldSerializationInfo, SerializerFunctionWrapHandler, SerializationInfo

from musify._types import StrippedString
from musify.local.exception import FileError
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
class M4A(LocalTrack[mutagen.mp4.MP4]):
    __final__ = True
    __supported_extensions__ = frozenset({"m4a"})

    class EmbeddedImage(LocalTrack.EmbeddedImage[mutagen.mp4.MP4Cover]):
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

    name: Annotated[StrippedString | None, TagAttribute()] = Field(
        description="A title of this track.",
        default=None,
        alias="©nam"
    )
    artists: Annotated[list[LocalArtist], TagAttribute(), TagAttribute("artist")] = Field(
        description="The artists featured on this track.",
        default_factory=list,
        alias="©ART"
    )
    album: Annotated[LocalAlbum | None, TagAttribute()] = Field(
        description="The album this track is featured on.",
        default=None,
        alias="©alb"
    )
    genres: Annotated[list[LocalGenre], TagAttribute(), TagAttribute("genre")] = Field(
        description="The genres associated with this track.",
        default_factory=list,
        validation_alias=AliasChoices("©gen", "gnre", "----:com.apple.iTunes:GENRE"),
        serialization_alias="©gen",
    )
    track: Annotated[Position | None, TagAttribute()] = Field(
        description="The position of the track on the album that this track is featured on.",
        default=None,
        alias="trkn"
    )
    disc: Annotated[Position | None, TagAttribute()] = Field(
        description="The position of the disc in the album that this track is featured on.",
        default=None,
        alias="disk"
    )
    bpm: Annotated[PositiveFloat | None, TagAttribute()] = Field(
        description="The tempo of this track.",
        default=None,
        alias="tmpo"
    )
    key: Annotated[KeySignature | None, TagAttribute()] = Field(
        description="The key of this track.",
        default=None,
        alias="----:com.apple.iTunes:INITIALKEY"
    )
    released_at: Annotated[SparseDate | None, TagAttribute()] = Field(
        description="The date this track was released.",
        default=None,
        alias="©day"
    )
    comments: Annotated[list[str], TagAttribute()] = Field(
        description="Freeform comments that are associated with this track.",
        default_factory=list,
        alias="©cmt"
    )
    images: Annotated[MutableMapping[str, ImageFile | ImageURL | EmbeddedImage] | None, TagAttribute()] = Field(
        description="Images associated with this track.",
        default=None,
        alias=EmbeddedImage.alias,
    )

    @computed_field(
        description="The main artist on the album.",
        alias="aART",
    )
    @property
    def album_artist(self) -> Annotated[LocalArtist | None, TagAttribute()]:
        return super().album_artist

    @album_artist.setter
    def album_artist(self, value: LocalArtist) -> None:
        super(type(self), type(self)).album_artist.fset(self, value)

    @computed_field(
        description="Whether the album is a compilation album.",
        alias="cpil",
    )
    @property
    def compilation(self) -> Annotated[bool | None, TagAttribute()]:
        return super().compilation

    @compilation.setter
    def compilation(self, value: bool | None) -> None:
        super(type(self), type(self)).compilation.fset(self, value)

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
    def _deserialize_free_form_fields[T:  Iterable](cls, value: T) -> T | list[str]:
        if not isinstance(value, tuple | list):
            return value
        return list(map(cls._deserialize_free_form_field, value))

    @model_serializer(mode="wrap")
    def _format_to_tags(self, handler: SerializerFunctionWrapHandler, info: SerializationInfo) -> dict[str, Any]:
        data = handler(self)
        if not info.by_alias or not isinstance(data, dict):  # not serializing to tag IDs
            return data

        self._convert_values_to_list(data)
        for key, val in data.items():
            if key.startswith("----:com.apple.iTunes:"):
                data[key] = [mutagen.mp4.MP4FreeForm(v.encode()) for v in val]
        return data

    @field_serializer("key", "released_at", mode="plain", when_used="unless-none")
    def _serialize_string(self, value: Any, info: SerializationInfo) -> str:
        if not info.by_alias or info.mode == "json":
            return value
        return str(value)

    @field_serializer("genres", "comments", mode="plain", when_used="unless-none")
    def _serialize_strings[T: Iterable[str]](self, value: T, info: FieldSerializationInfo) -> T | list[str]:
        if not info.by_alias and info.mode != "json":  # not serializing to tag IDs
            return value

        values = self._extract_names(value)
        self._extend_with_uris(values, info=info)
        return list(map(str, values))

    @field_serializer("album", "album_artist", mode="plain", when_used="unless-none")
    def _serialize_name(self, value: str | HasName, info: SerializationInfo) -> str | None:
        if info.by_alias or info.mode == "json":
            return self._extract_name(value)
        return self._extract_name(value)

    @field_serializer("artists", mode="plain", when_used="unless-none")
    def _serialize_names(self, value: Iterable[str | HasName], info: SerializationInfo) -> str | list[str]:
        if info.mode == "json":
            return self._extract_names(value)
        return self._join_split_tags(value)

    @field_serializer("bpm", mode="plain", when_used="unless-none")
    def _serialize_bpm[T: int | float](self, value: T, info: FieldSerializationInfo) -> T | list[int] | None:
        if not info.by_alias:  # not serializing to tag IDs
            return value
        if not isinstance(value, int | float):
            return
        return [int(value)]

    @field_serializer("track", "disc", mode="plain", when_used="unless-none")
    def _serialize_position_tags[T: Position](self, value: T, info: FieldSerializationInfo) -> T | list[tuple] | None:
        if not info.by_alias:  # not serializing to tag IDs
            return value
        if not isinstance(value, Position):
            return
        return [value.numbers]
