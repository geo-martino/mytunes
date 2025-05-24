import types
from collections.abc import Iterable, Collection
from typing import Any, Literal, get_args

import mutagen.flac
import mutagen.id3
from pydantic import Field, AliasChoices, model_validator, field_validator

from musify.local.item.track import LocalTrack
from musify.model.properties.date import SparseDate
from musify.model.properties.image import get_picture_name_from_id3_value
from musify.model.properties.music import KeySignature
from musify.model.properties.order import Position


class FLAC(LocalTrack[mutagen.flac.FLAC]):
    format: Literal["flac"] = Field(
        description="The format (or file type) of the file.",
        validation_alias=AliasChoices("ext", "extension"),
        default=None,
        exclude=True,
    )

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

    # noinspection PyNestedDecorators
    @field_validator("images", mode="before")
    @staticmethod
    def _deserialize_from_pictures[T](
            pictures: T | bytes | mutagen.flac.Picture | Collection[mutagen.flac.Picture]
    ) -> T | dict[int, bytes]:
        if isinstance(pictures, mutagen.flac.Picture):
            pictures = [pictures]
        if not isinstance(pictures, tuple | list):
            return pictures
        elif not all(isinstance(img, mutagen.flac.Picture) for img in pictures):
            return pictures

        return {img.type: img.data for img in pictures}
