from abc import ABCMeta, abstractmethod
from collections.abc import Collection, Mapping, MutableMapping, MutableSequence
from copy import copy
from io import BytesIO
from pathlib import Path
from typing import Self, Any, Literal, ClassVar

import mutagen
import mutagen.id3
from PIL import Image
from pydantic import field_validator, model_validator, validate_call, AliasChoices, ModelWrapValidatorHandler, \
    InstanceOf, field_serializer
# noinspection PyProtectedMember
from pydantic.fields import Field, FieldInfo
from pydantic_core.core_schema import FieldSerializationInfo

from musify.local._base import LocalResource
from musify.local.exception import FileError
from musify.local.item.album import LocalAlbum
from musify.local.item.artist import LocalArtist
from musify.local.item.genre import LocalGenre
from musify.model import MusifyModel
from musify.model.item.track import Track, TrackTagsMixin
from musify.model.properties.file import IsFile
from musify.model.properties.image import FileEmbeddedImage, ImageSource
from musify.model.properties.name import HasName
from musify.model.properties.order import Position
from musify.model.properties.uri import HasMutableURI


class TagDumpContext[T](MusifyModel):
    map_uri_to_tag: Literal["comments"] = Field(
        description=(
            "The tag type to use for storing the URIs of the track. "
            "By default, the URIs will not be dumped to any tag."
        ),
        default="comments"
    )
    loaded_images: Mapping[str, InstanceOf[Image.Image]] = Field(
        description="The image properties and their loaded images.",
        default_factory=dict
    )


class LocalTrack[T: mutagen.FileType](
    LocalResource, Track[LocalArtist, LocalAlbum, LocalGenre], IsFile, HasMutableURI
):
    class EmbeddedImage[FT: mutagen.FileType, TT](FileEmbeddedImage, metaclass=ABCMeta):
        alias: ClassVar[str | AliasChoices] = "images"

        # noinspection PyNestedDecorators
        @model_validator(mode="wrap")
        @classmethod
        def _from_tag_value(cls, value: TT, handler: ModelWrapValidatorHandler[Self]) -> Self:
            img_bytes = cls._get_bytes(value)
            if not isinstance(img_bytes, bytes):
                return handler(value)

            img = Image.open(BytesIO(img_bytes))
            obj = handler(img)
            del img

            img_type = cls.get_id3_type_from_tag(value)
            if img_type:
                obj.type = img_type
            return obj

        @classmethod
        def from_image_model(cls, model: ImageSource) -> Self:
            """Create an instance of an this image model from any other type of ImageSource model."""
            if isinstance(model, cls):
                return model

            # noinspection PyTypeChecker
            dump = model.model_dump(
                include=set(model.__class__.model_fields) & set(cls.model_fields),
                exclude_none=True,
                exclude_defaults=True,
                exclude_unset=True
            )
            return cls(**dump)

        async def _get_file(self, file: FT = None) -> FT:
            if isinstance(file, mutagen.FileType):
                if self.path is not None and Path(file.filename or "") != self.path:
                    raise FileError("Given file does not match the path of this image.")
                return file

            if self.path is None:
                raise FileError("Path is not set and no loaded file was given, cannot load image.")
            return await LocalTrack.load_file(self.path)

        async def _get_tag_value(self, file: FT = None) -> Any:
            file = await self._get_file(file)
            return file.tags.get(self.alias)

        @staticmethod
        def _get_image_data(image: bytes | Image.Image) -> tuple[Image. Image, bytes]:
            if isinstance(image, bytes):
                data = image
                image = Image.open(BytesIO(data))
            else:
                data = BytesIO()
                image.save(data, format=image.format)
                data = data.getvalue()

            return image, data

        @classmethod
        @abstractmethod
        def _get_bytes[T](cls, value: T | TT) -> T | bytes | None:
            raise NotImplementedError

        @classmethod
        @abstractmethod
        def get_id3_type_from_tag(cls, value: TT) -> str | None:
            """Get the ID3 type from the given attribute."""
            raise NotImplementedError

        async def load(self, file: FT = None) -> Image.Image | None:
            for attr in await self._get_tag_value(file):
                id3_type = self.get_id3_type_from_tag(attr)
                if id3_type == self.type:
                    img_bytes = self._get_bytes(attr)
                    return Image.open(BytesIO(img_bytes))

        @abstractmethod
        def build(self, image: bytes | Image.Image | None) -> TT:
            """Builds the image tag object for serialization."""
            raise NotImplementedError

    @classmethod
    @validate_call
    async def from_file(cls, path: str | Path) -> Self:
        file = await cls.load_file(path)
        # some subclasses need to access the file obj on construction so just pass the file obj
        # noinspection PyArgumentList
        return cls.model_validate(file)

    @classmethod
    @validate_call
    async def load_file(cls, path: str | Path) -> T:
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
        if isinstance(value, tuple | list) and len(value) >= 1:
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

    def _serialize_position_tags(self, value: Position, info: FieldSerializationInfo) -> Any:
        if not info.by_alias:  # not serializing to tag IDs
            return value

        field: FieldInfo = self.__class__.model_fields[info.field_name]
        if not isinstance(field.validation_alias, AliasChoices):
            return str(value)

        aliases = [al for al in field.validation_alias.choices if isinstance(al, str)]
        data = dict(zip(aliases, (value.number, value.total)))
        return {k: str(v).zfill(value.zero_fill) for k, v in data.items() if v is not None}

    @staticmethod
    def _flatten_dump(data: MutableMapping[str, Any]) -> None:
        for key, val in copy(data).items():
            if isinstance(val, Mapping):
                data |= data.pop(key)

    @staticmethod
    def _convert_values_to_list(data: MutableMapping[str, Any]) -> None:
        for key, val in data.items():
            if not isinstance(val, (tuple, list)):
                data[key] = [val]

    def _extend_with_uris(self, values: MutableSequence[Any], info: FieldSerializationInfo) -> None:
        context = info.context
        if self.uris and isinstance(context, TagDumpContext) and context.map_uri_to_tag == info.field_name:
            values.extend(self.uris)

    # noinspection PyNestedDecorators
    @field_validator("images", mode="before")
    @classmethod
    def _map_images(cls, images: Any) -> Any:
        if not isinstance(images, tuple | list):
            return images

        mapped_images = {}
        for image in images:
            if isinstance(image, ImageSource):
                key = image.type
            else:
                key = cls.EmbeddedImage.get_id3_type_from_tag(image)

            if key is None:
                key = mutagen.id3.PictureType.COVER_FRONT
            if key not in mapped_images:
                mapped_images[key] = image

        return mapped_images

    @field_serializer("images", mode="plain", when_used="unless-none")
    def _serialize_images(self, images: Any, info: FieldSerializationInfo) -> Any:
        if not info.by_alias:  # if not serializing to tag IDs, return the images models
            return images

        context = info.context
        if not isinstance(context, TagDumpContext) or not context.loaded_images:
            return []
        if missing_images := set(context.loaded_images) - set(self.images or ()):
            raise FileError(f"Some image types are missing from the loaded images: {", ".join(missing_images)}")

        return [
            self.EmbeddedImage.from_image_model(model).build(context.loaded_images[kind])
            for kind, model in self.images.items()
        ]

    @classmethod
    def _get_tag_id(cls, name: str) -> str | None:
        field: FieldInfo = cls.model_fields[name]
        tag_id = None
        if isinstance(field.serialization_alias, str):
            tag_id = field.serialization_alias
        elif isinstance(field.alias, str):
            tag_id = field.alias
        elif isinstance(field.validation_alias, str):
            tag_id = field.validation_alias
        elif isinstance(field.validation_alias, AliasChoices):
            tag_id = next(iter(field.validation_alias.choices))

        return tag_id

    async def to_tags(self, context: TagDumpContext[T] = None) -> dict[str, Any]:
        include_fields = {*TrackTagsMixin.model_fields}
        return self.model_dump(include=include_fields, context=context, by_alias=True, exclude_none=True)

    async def load(self) -> Any:
        model = await self.from_file(self.path)
        self.__dict__ = model.__dict__
        del model

    async def save(self, *args, **kwargs) -> Any:
        pass  # TODO

    async def clear_tags(self) -> None:
        pass  # TODO
