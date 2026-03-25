from collections.abc import MutableMapping, Iterable, Sequence
from typing import Any, Self, final, Annotated

import mutagen.flac
import mutagen.id3
from PIL import Image, ImageFile as PILImageFile
from pydantic import Field, AliasChoices, model_validator, field_serializer, model_serializer, \
    ModelWrapValidatorHandler, NonNegativeFloat, ConfigDict
from pydantic_core.core_schema import SerializerFunctionWrapHandler, SerializationInfo, FieldSerializationInfo

from musify.local.item.artist import LocalArtist
from musify.local.item.genre import LocalGenre
from musify.local.item.track import LocalTrack
from musify.models.metadata import TagAttribute
from musify.models.properties.date import SparseDate
from musify.models.properties.image import ImageFile, ImageURL
from musify.models.properties.music import KeySignature
from musify.models.properties.name import HasName
from musify.models.properties.order import Position
from musify.models.properties.rating import Rating
from musify.utils import get_base_types


@final
class FLAC(LocalTrack[mutagen.flac.FLAC]):
    __final__ = True
    __supported_extensions__ = frozenset({"flac"})

    model_config = ConfigDict(
        # catches fields like albumartist etc.
        alias_generator=lambda name: name.lower().replace("_", "")
    )

    class EmbeddedImage(LocalTrack.EmbeddedImage[mutagen.flac.Picture]):
        @classmethod
        def _get_bytes(cls, value: Any) -> Any:
            return value.data if isinstance(value, mutagen.flac.Picture) else value

        @classmethod
        def get_id3_type_from_tag(cls, value: mutagen.flac.Picture) -> str | None:
            return cls._get_type_from_number(value.type) if isinstance(value, mutagen.flac.Picture) else None

        async def _get_tag_value(self, file: mutagen.flac.FLAC = None) -> mutagen.flac.Picture | None:
            file = await self._get_file(file)
            return next((pic for pic in file.pictures if pic.type == self.id3_type), None)

        def build(self, image: bytes | PILImageFile.ImageFile | None) -> mutagen.flac.Picture | None:
            if image is None:
                return

            image, data = self._get_image_data(image)

            picture = mutagen.flac.Picture()
            picture.type = self.id3_type
            picture.mime = Image.MIME[image.format]
            picture.data = data

            return picture

    artists: Annotated[list[LocalArtist], TagAttribute(), TagAttribute("artist")] = Field(
        description="The artists featured on this track.",
        default_factory=list,
        alias="artist",
    )
    genres: Annotated[list[LocalGenre], TagAttribute(), TagAttribute("genre")] = Field(
        description="The genres associated with this track.",
        default_factory=list,
        alias="genre",
    )
    track: Annotated[Position | None, TagAttribute()] = Field(
        description="The position of the track in the album that this track is featured on.",
        default=None,
        validation_alias=AliasChoices("tracknumber", "tracktotal"),
        serialization_alias="tracknumber",
    )
    disc: Annotated[Position | None, TagAttribute()] = Field(
        description="The position of the disc in the album that this track is featured on.",
        default=None,
        validation_alias=AliasChoices("discnumber", "disctotal"),
        serialization_alias="discnumber",
    )
    released_at: Annotated[SparseDate | None, TagAttribute()] = Field(
        description="The date this track was released.",
        default=None,
        validation_alias=AliasChoices("date", "release date", "year"),
        serialization_alias="date",
    )
    key: Annotated[KeySignature | None, TagAttribute()] = Field(
        description="The key of this track.",
        default=None,
        alias="initialkey",
    )
    rating: Annotated[Rating[NonNegativeFloat] | None, TagAttribute()] = Field(
        description="The rating of this track.",
        default=None,
    )
    comments: Annotated[list[str], TagAttribute()] = Field(
        description="Freeform comments that are associated with this track.",
        default_factory=list,
        validation_alias=AliasChoices("comment", "description"),
        alias="comment",
    )
    images: Annotated[MutableMapping[str, ImageFile | ImageURL | EmbeddedImage] | None, TagAttribute()] = Field(
        description="Images associated with this track.",
        default=None,
    )

    @classmethod
    def _extract_tags_from_mutagen(cls, file: mutagen.flac.FLAC) -> dict[str, Any]:
        # noinspection PyCallingNonCallable
        data = super()._extract_tags_from_mutagen(file)
        data |= dict(images=file.pictures)
        data.pop("source", None)  # clashes with HasMutableURI field
        return data

    # noinspection PyNestedDecorators
    @model_validator(mode="wrap")
    @classmethod
    def _merge_position_values(cls, data: MutableMapping[str, Any], handler: ModelWrapValidatorHandler[Self]) -> Self:
        if not isinstance(data, MutableMapping):
            return handler(data)

        for name, field in cls.model_fields.items():
            if not isinstance(field.validation_alias, AliasChoices) or isinstance(data.get(name, None), Position):
                continue
            if Position not in get_base_types(field.annotation):
                continue

            aliases = (al for al in field.validation_alias.choices if isinstance(al, str))
            values = []
            if cls.model_config.get("validate_by_name") and data.get(name, None) is not None:
                value = data.pop(name)
                values.extend(value) if isinstance(value, Sequence) else values.append(value)
                # assume first alias choice is an alias for the position number
                # look for total number from 2nd alias choice onward
                next(aliases)

            values.extend(filter(None, (data.pop(alias, None) for alias in aliases)))
            values[:] = list(map(cls._extract_first_value_from_sequence, values))
            if len(values) > 1:
                # if multiple values with divider, assume first is position, second is total
                values[:] = [str(v).split("/")[min(len(str(v).split("/")) - 1, i)] for i, v in enumerate(values)]
            if values:
                data[name] = tuple(values)

        return handler(data)

    @model_serializer(mode="wrap")
    def _format_to_tags(self, handler: SerializerFunctionWrapHandler, info: SerializationInfo) -> dict[str, Any]:
        data = handler(self)
        if not info.by_alias or not isinstance(data, dict):  # not serializing to tag IDs
            return data

        self._flatten_dump(data)
        self._convert_values_to_list(data)
        return data

    @field_serializer(
        "key", "bpm", "released_at",
        mode="plain", when_used="unless-none",
    )
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

    @field_serializer("compilation", mode="plain", when_used="unless-none")
    def _serialize_bool[T: bool](self, value: T, info: FieldSerializationInfo) -> str:
        if not info.by_alias and info.mode != "json":
            return value
        return str(int(value))

    @field_serializer("album", "album_artist", mode="plain", when_used="unless-none")
    def _serialize_name(self, value: str | HasName, info: SerializationInfo) -> str | None:
        if not info.by_alias and info.mode == "json":
            return self._extract_name(value)
        return self._extract_name(value)

    @field_serializer("artists", mode="plain", when_used="unless-none")
    def _serialize_names(self, value: Iterable[str | HasName], info: SerializationInfo) -> str | list[str]:
        if info.mode == "json":
            return self._extract_names(value)
        return self._join_split_tags(value)

    @field_serializer("track", "disc", mode="plain", when_used="unless-none")
    def _serialize_position_tags(self, value: Position, info: FieldSerializationInfo) -> str | dict[str, str] | None:
        return super()._serialize_position_tags(value, info=info)
