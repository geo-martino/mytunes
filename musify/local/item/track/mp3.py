from collections.abc import MutableSequence, MutableMapping, Iterable
from copy import copy
from typing import Any, ClassVar, Self, final, Annotated

import mutagen.id3
import mutagen.mp3
from PIL import Image, ImageFile as PILImageFile
from pydantic import Field, AliasChoices, PositiveFloat, InstanceOf, model_validator, model_serializer, \
    field_validator, field_serializer, ModelWrapValidatorHandler, NonNegativeFloat, computed_field
from pydantic_core.core_schema import SerializerFunctionWrapHandler, FieldSerializationInfo, SerializationInfo

from musify._types import StrippedString
from musify.local.item.album import LocalAlbum
from musify.local.item.artist import LocalArtist
from musify.local.item.genre import LocalGenre
from musify.local.item.track import LocalTrack
from musify.local.item.track._base import TagContext
from musify.models.metadata import TagAttribute
from musify.models.properties.date import SparseDate
from musify.models.properties.image import ImageURL, ImageFile
from musify.models.properties.music import KeySignature
from musify.models.properties.name import HasName
from musify.models.properties.order import Position
from musify.models.properties.rating import Rating


@final
class MP3(LocalTrack[mutagen.mp3.MP3]):
    __supported_extensions__ = frozenset({"mp3"})
    __final__ = True

    class EmbeddedImage(LocalTrack.EmbeddedImage[mutagen.id3.APIC]):
        alias: ClassVar[str] = "APIC"

        @classmethod
        def _get_bytes(cls, value: Any) -> Any:
            return value.data if isinstance(value, mutagen.id3.APIC) else value

        @classmethod
        def get_id3_type_from_tag(cls, value: mutagen.id3.APIC) -> str | None:
            if not isinstance(value, mutagen.id3.APIC):
                return
            return cls._get_type_from_number(int(value.type))

        def build(self, image: bytes | PILImageFile.ImageFile | None) -> mutagen.id3.APIC | None:
            if image is None:
                return

            image, data = self._get_image_data(image)
            return mutagen.id3.APIC(
                encoding=mutagen.id3.Encoding.UTF8,
                mime=Image.MIME[image.format],
                type=self.id3_type,
                data=data,
            )

    name: Annotated[StrippedString | None, TagAttribute()] = Field(
        description="A title of this track.",
        default=None,
        alias="TIT2",
    )
    artists: Annotated[list[LocalArtist], TagAttribute(), TagAttribute("artist")] = Field(
        description="The artists featured on this track.",
        default_factory=list,
        alias="TPE1",
    )
    album: Annotated[LocalAlbum | None, TagAttribute()] = Field(
        description="The album this track is featured on.",
        default=None,
        alias="TALB",
    )
    genres: Annotated[list[LocalGenre], TagAttribute(), TagAttribute("genre")] = Field(
        description="The genres associated with this track.",
        default_factory=list,
        alias="TCON",
    )
    track: Annotated[Position | None, TagAttribute()] = Field(
        description="The position of the track on the album that this track is featured on.",
        default=None,
        alias="TRCK",
    )
    disc: Annotated[Position | None, TagAttribute()] = Field(
        description="The position of the disc in the album that this track is featured on.",
        default=None,
        alias="TPOS",
    )
    bpm: Annotated[PositiveFloat | None, TagAttribute()] = Field(
        description="The tempo of this track.",
        default=None,
        alias="TBPM",
    )
    key: Annotated[KeySignature | None, TagAttribute()] = Field(
        description="The key of this track.",
        default=None,
        alias="TKEY",
    )
    released_at: Annotated[SparseDate | None, TagAttribute()] = Field(
        description="The date this track was released.",
        default=None,
        validation_alias=AliasChoices("TDAT", "TDOR", "TYER", "TORY", "TDRC"),
        serialization_alias="TDAT",
    )
    rating: Annotated[Rating[NonNegativeFloat] | None, TagAttribute()] = Field(
        description="The rating of this track.",
        default=None,
        alias="POPM",
    )
    comments: Annotated[list[str], TagAttribute()] = Field(
        description="Freeform comments that are associated with this track.",
        default_factory=list,
        validation_alias=AliasChoices("COMM", "COMMENT"),
        serialization_alias="COMM",
    )
    images: Annotated[MutableMapping[str, ImageFile | ImageURL | EmbeddedImage] | None, TagAttribute()] = Field(
        description="Images associated with this track.",
        default=None,
        alias=EmbeddedImage.alias,
    )

    @computed_field(
        description="The main artist on the album.",
        alias="TPE2",
    )
    def album_artist(self) -> Annotated[LocalArtist | None, TagAttribute()]:
        return super().album_artist

    @album_artist.setter
    def album_artist(self, value: LocalArtist) -> None:
        value = self._deserialize_text_frame(value)
        super(type(self), type(self)).album_artist.fset(self, value)

    @computed_field(
        description="Whether the album is a compilation album.",
        alias="TCMP",
    )
    def compilation(self) -> Annotated[bool | None, TagAttribute()]:
        return super().compilation

    @compilation.setter
    def compilation(self, value: bool | None) -> None:
        value = self._deserialize_text_frame(value)
        super(type(self), type(self)).compilation.fset(self, value)

    @classmethod
    def _get_frame_class(cls, info: FieldSerializationInfo) -> type[mutagen.id3.Frame]:
        tag_id = cls._get_tag_id(info.field_name)
        return getattr(mutagen.id3, tag_id)

    # noinspection PyNestedDecorators
    @model_validator(mode="wrap")
    @classmethod
    def _merge_suffixed_tags(
            cls, file: mutagen.mp3.MP3 | MutableMapping[str, Any], handler: ModelWrapValidatorHandler[Self]
    ) -> Self:
        data = cls._extract_tags_from_mutagen(file) if isinstance(file, mutagen.mp3.MP3) else file
        if not isinstance(data, MutableMapping):
            return handler(data)

        for key in list(data):
            key_prefix = key.split(":")[0]
            if key_prefix.startswith("COMM"):  # special case to merge comment keys correctly
                key_prefix = "COMM"
            if key_prefix == key:
                continue

            if key_prefix not in data:
                data[key_prefix] = []
            elif not isinstance(val_prefix := data[key_prefix], MutableSequence):
                data[key_prefix] = [val_prefix]

            data[key_prefix].append(data.pop(key))

        return handler(data)

    # noinspection PyNestedDecorators
    @model_serializer(mode="wrap")
    def _format_to_tags(
            self, handler: SerializerFunctionWrapHandler, info: SerializationInfo
    ) -> dict[str, Any]:
        data = handler(self)
        if not info.by_alias or not isinstance(data, dict):  # not serializing to tag IDs
            return data

        for tag_id, tag_value in copy(data).items():
            if not isinstance(tag_value, tuple | list):
                continue

            for i, frame in enumerate(tag_value, 1):
                match frame:
                    case mutagen.id3.COMM():
                        # noinspection PyUnresolvedReferences
                        tag_parts = (tag_id, frame.desc or str(i), frame.lang or None)
                    case mutagen.id3.APIC():
                        tag_type = next(
                            (name for name, enum in vars(mutagen.id3.PictureType).items() if enum == frame.type), str(i)
                        )
                        tag_parts = (tag_id, tag_type)
                    case _:
                        tag_parts = (tag_id,)

                data[":".join(filter(None, tag_parts))] = frame

            data.pop(tag_id)

        return data

    # noinspection PyNestedDecorators
    @field_validator(
        "name", "album", "track", "disc", "bpm", "key", "released_at", "uri",
        mode="before"
    )
    @classmethod
    def _deserialize_text_frame[T](cls, value: T) -> T | str:
        # parent class validators always execute after child class validators
        # need to manually call required upstream parent validators here
        value = cls._extract_first_value_from_single_sequence(value)
        if not isinstance(value, mutagen.id3.TextFrame):
            return value

        return str(value)

    # noinspection PyNestedDecorators
    @field_validator(
        "artists", "genres", "comments",
        mode="before"
    )
    @classmethod
    def _deserialize_text_frames[T](cls, value: T | Iterable[mutagen.id3.TextFrame]) -> T | list[str]:
        if value is None:
            return value
        if not isinstance(value, tuple | list):
            value = [value]

        return list(map(cls._deserialize_text_frame, value))

    # noinspection PyNestedDecorators
    @field_validator("rating", mode="before")
    @classmethod
    def _deserialize_rating_frame[T](cls, value: T) -> T | str:
        value = cls._extract_first_value_from_single_sequence(value)
        if not isinstance(value, mutagen.id3.POPM):
            return value

        # noinspection PyUnresolvedReferences
        return value.rating

    @field_serializer("compilation", mode="plain", when_used="unless-none")
    def _serialize_bool[T: bool](self, value: T, info: FieldSerializationInfo) -> str:
        if not info.by_alias and info.mode != "json":
            return value
        return self._serialize_text_frame(str(int(value)), info=info)

    @field_serializer("album", "album_artist", mode="plain", when_used="unless-none")
    def _serialize_name[T: str | HasName](
            self, value: T, info: SerializationInfo
    ) -> T | str | InstanceOf[mutagen.id3.TextFrame]:
        if info.mode == "json":
            return self._extract_name(value)
        # noinspection PyArgumentList
        return self._serialize_text_frame(value, info=info)

    @field_serializer("artists", "genres", mode="plain", when_used="unless-none")
    def _serialize_names[T: Iterable[str | HasName]](
        self, value: T, info: FieldSerializationInfo
    ) -> T | list[str] | InstanceOf[mutagen.id3.TextFrame]:
        if info.mode == "json":
            return self._extract_names(value)
        # noinspection PyArgumentList
        return self._serialize_text_frame(value, info=info)

    # noinspection PyNestedDecorators
    @field_serializer(
        "name", "track", "disc", "bpm", "key", "released_at",
        mode="plain", when_used="unless-none"
    )
    def _serialize_text_frame[T](
            self, value: T | str | HasName, info: FieldSerializationInfo
    ) -> T | InstanceOf[mutagen.id3.TextFrame]:
        if not info.by_alias or info.mode == "json":  # not serializing to tag IDs
            return value
        if not isinstance(value, tuple | list):
            value = [value]

        frame_cls = self._get_frame_class(info)
        tag_value = self._join_split_tags(value)
        return frame_cls(text=tag_value)

    @field_serializer("comments", mode="plain", when_used="unless-none")
    def _serialize_text_frames[T](
            self, values: T | Iterable[str | HasName], info: FieldSerializationInfo
    ) -> T | list[InstanceOf[mutagen.id3.TextFrame]]:
        if not info.by_alias or info.mode == "json":  # not serializing to tag IDs
            return values

        frame_cls = self._get_frame_class(info)
        values: list[frame_cls] = [frame_cls(text=item, lang="eng") for item in values]

        context = info.context
        if self.uris and isinstance(context, TagContext) and context.map_uri_to_field == info.field_name:
            values.extend(frame_cls(text=str(uri), desc=f"{uri.source}URI", lang="eng") for uri in self.uris)

        return values

    @staticmethod
    def _clear_tag(file: mutagen.mp3.MP3, tag_id: str) -> set[str]:
        removed = set()
        for tag_key in file.tags:
            if tag_key.casefold().startswith(tag_id.casefold()):
                del file.tags[tag_key]
                removed.add(tag_key)

        return removed
