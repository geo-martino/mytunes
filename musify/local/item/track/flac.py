import types
from collections.abc import MutableMapping
from typing import Any, Literal, get_args

import mutagen.flac
import mutagen.id3
from PIL import Image
from pydantic import Field, AliasChoices, model_validator

from musify.local.item.track import LocalTrack
from musify.model.properties.date import SparseDate
from musify.model.properties.image import ImageFile, ImageURL
from musify.model.properties.music import KeySignature
from musify.model.properties.order import Position


class FLAC(LocalTrack[mutagen.flac.FLAC]):
    format: Literal["flac"]

    class EmbeddedImage(LocalTrack.EmbeddedImage[mutagen.flac.FLAC, mutagen.flac.Picture]):
        @classmethod
        def _get_bytes(cls, value: Any) -> Any:
            return value.data if isinstance(value, mutagen.flac.Picture) else value

        @classmethod
        def get_id3_type_from_tag(cls, value: mutagen.flac.Picture) -> str | None:
            return cls._get_type_from_number(value.type) if isinstance(value, mutagen.flac.Picture) else None

        async def _get_tag_value(self, file: mutagen.flac.FLAC = None) -> mutagen.flac.Picture | None:
            file = await self._get_file(file)
            return next((pic for pic in file.pictures if pic.type == self.id3_type), None)

        def build(self, image: bytes | Image.Image | None) -> mutagen.flac.Picture | None:
            if image is None:
                return

            image, data = self._get_image_data(image)

            picture = mutagen.flac.Picture()
            picture.type = self.id3_type
            picture.mime = Image.MIME[image.format]
            picture.data = data

            return picture

    track: Position | None = Field(
        validation_alias=AliasChoices("tracknumber", "tracktotal"),
        default=None,
    )
    disc: Position | None = Field(
        description="The position of the disc in the album that this track is featured on.",
        default=None,
        validation_alias=AliasChoices("discnumber", "disctotal")
    )
    released_at: SparseDate | None = Field(
        description="The date this track was released.",
        default=None,
        validation_alias=AliasChoices("date", "release date", "year")
    )
    key: KeySignature | None = Field(
        description="The key of this track.",
        default=None,
        validation_alias="initialkey",
    )
    comments: list[str] = Field(
        description="Freeform comments that are associated with this track.",
        default_factory=list,
        validation_alias=AliasChoices("comment", "description"),
    )
    images: MutableMapping[str, ImageFile | ImageURL | EmbeddedImage] | None = Field(
        description="Images associated with this track.",
        default=None,
    )

    # noinspection PyNestedDecorators
    @model_validator(mode="before")
    @classmethod
    def _extract_tags_from_mutagen[T](cls, file: T) -> T | dict[str, Any]:
        if not isinstance(file, mutagen.flac.FLAC):
            return file

        # noinspection PyCallingNonCallable
        tags = super()._extract_tags_from_mutagen(file)
        return tags | dict(images=file.pictures)

    # noinspection PyNestedDecorators
    @model_validator(mode="before")
    @classmethod
    def _merge_position_values[T](cls, value: T) -> T | dict[str, Any]:
        if not isinstance(value, dict):
            return value

        for name, field in cls.model_fields.items():
            if not isinstance(field.validation_alias, AliasChoices):
                continue

            if isinstance(field.annotation, types.UnionType):
                if Position not in get_args(field.annotation):
                    continue
            elif field.annotation is not Position:
                continue

            aliases = (al for al in field.validation_alias.choices if isinstance(al, str))
            values = []
            if cls.model_config.get("validate_by_name") and value.get(name, None) is not None:
                values.append(value.pop(name))
                # assume first alias choice is an alias for the position number
                # look for total number from 2nd alias choice onward
                next(aliases)

            values.extend(filter(None, (value.pop(alias, None) for alias in aliases)))
            value[field.validation_alias.choices[0]] = tuple(map(cls._extract_first_value_from_sequence, values))

        return value
