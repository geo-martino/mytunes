from collections.abc import Collection
from pathlib import Path
from typing import Self, Any

import mutagen
import mutagen.id3
from pydantic import field_validator, model_validator, validate_call, AliasChoices
from pydantic.fields import FieldInfo

from musify.local._base import LocalResource
from musify.local.item.album import LocalAlbum
from musify.local.item.artist import LocalArtist
from musify.local.item.genre import LocalGenre
from musify.model.item.track import Track, TrackTagsMixin
from musify.model.properties.file import IsFile
from musify.model.properties.name import HasName
from musify.model.properties.uri import HasMutableURI


class LocalTrack[T: mutagen.FileType](LocalResource, Track[LocalArtist, LocalAlbum, LocalGenre], IsFile, HasMutableURI):
    __tags_deleted: set[str] = set()

    @classmethod
    @validate_call
    async def from_file(cls, path: str | Path) -> Self:
        file = await cls._load_mutagen(path)
        # some subclasses need to access the file obj on construction so just pass the file obj
        # noinspection PyArgumentList
        return cls.model_validate(file)

    @classmethod
    @validate_call
    async def _load_mutagen(cls, path: str | Path) -> T:
        # TODO: figure out how to load file asynchronously here to improve IO-bound performance
        with Path(path).open("rb") as f:
            file = mutagen.File(f)
            file.filename = str(path)

        return file

    # noinspection PyNestedDecorators
    @model_validator(mode="before")
    @classmethod
    def _extract_tags_from_mutagen[F](cls, file: F) -> F | dict[str, Any]:
        if not isinstance(file, mutagen.FileType):
            return file

        return dict(file.tags) | dict(path=file.filename)

    # noinspection PyNestedDecorators
    @field_validator(
        "name", "album", "bpm", "key", "uri",
        mode="before", check_fields=False
    )
    @staticmethod
    def _extract_first_value_from_sequence(value: Any) -> str | None:
        if isinstance(value, tuple | list):
            value = value[0]
        return value

    # noinspection PyNestedDecorators
    @field_validator(
        "name", "album", "track", "disc", "bpm", "key", "released_at", "uri",
        mode="before", check_fields=False
    )
    @staticmethod
    def _extract_first_value_from_single_sequence(value: Any) -> str | None:
        if isinstance(value, tuple | list) and len(value) == 1:
            value = value[0]
        return value

    # noinspection PyNestedDecorators
    @field_validator(
        "name", "artists", "album", "genres", "track", "disc", "bpm", "key", "released_at", "uri",
        mode="before", check_fields=False
    )
    @staticmethod
    def _nullify[T](value: T) -> T | None:
        match value:
            case Collection() if len(value) == 0:
                return
            case Collection() if all(isinstance(v, str) and not v for v in value):
                return
            case _:
                return value

    # noinspection PyNestedDecorators
    @field_validator(
        "genres", "comments",
        mode="before", check_fields=False
    )
    @classmethod
    def _split_joined_tags[T](cls, value: T) -> T | list[str]:
        if not isinstance(value, tuple | list) or not all(isinstance(v, str) for v in value):
            return value
        return [v for item in value for v in cls._separate_tags(item)]

    @classmethod
    def _join_split_tags(cls, value: list[Any]) -> str:
        values = [v.name if isinstance(v, HasName) else v for v in value]
        return cls._join_tags(str(v) for v in values if v and str(v))

    @classmethod
    def _get_tag_id(cls, name: str) -> str | None:
        field: FieldInfo = cls.model_fields[name]
        tag_id = None
        if isinstance(field.alias, str):
            tag_id = field.alias
        elif isinstance(field.serialization_alias, str):
            tag_id = field.serialization_alias
        elif isinstance(field.validation_alias, str):
            tag_id = field.validation_alias
        elif isinstance(field.validation_alias, AliasChoices):
            tag_id = next(iter(field.validation_alias.choices))

        return tag_id

    def to_tags(self) -> dict[str, Any]:
        include_fields = {*TrackTagsMixin.model_fields}
        context = {"uri": "comments"}
        return self.model_dump(include=include_fields, context=context, by_alias=True, exclude_none=True)

    async def load(self) -> Any:
        model = await self.from_file(self.path)
        self.__dict__ = model.__dict__
        del model

    async def save(self, *args, **kwargs) -> Any:
        pass  # TODO

    async def clear_tags(self) -> None:
        pass  # TODO
