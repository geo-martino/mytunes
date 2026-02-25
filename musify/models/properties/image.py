from __future__ import annotations

from abc import ABCMeta, abstractmethod
from collections.abc import Mapping, MutableMapping
from http import HTTPMethod
from io import BytesIO
from pathlib import Path
from typing import Self, ClassVar

import aiofiles
import aiohttp
import mutagen.id3
from PIL import Image, ImageFile as PILImageFile
from pydantic import InstanceOf, Field, PositiveInt, field_validator, model_validator
from pydantic.functional_validators import ModelWrapValidatorHandler
from yarl import URL

from musify._types import StrippedString, UpperSnakeCase
from musify.exception import MusifyValueError
from musify.models._base import MusifyModel, AttributeResource


class ImageBase(MusifyModel):
    """Represents an image."""
    # noinspection PyTypeChecker
    __type_map: ClassVar[Mapping[str, mutagen.id3.PictureType]] = {
        name: enum for name, enum in vars(mutagen.id3.PictureType).items()
        if isinstance(enum, mutagen.id3.PictureType)
    }

    type: UpperSnakeCase = Field(
        description="The type of the image, as defined by ID3 tags.",
        default="COVER_FRONT",
    )
    mime: StrippedString | None = Field(
        description="The MIME type of the image.",
        default=None,
    )
    description: StrippedString | None = Field(
        description="A description of the image.",
        default=None,
    )
    height: PositiveInt | None = Field(
        description="The height of the image in pixels.",
        default=None,
    )
    width: PositiveInt | None = Field(
        description="The width of the image in pixels.",
        default=None,
    )

    @property
    def id3_type(self) -> mutagen.id3.PictureType:
        """Return the ID3 value for the image type."""
        name = str(self.type).upper().replace(" ", "_")
        return self.__type_map[name]

    # noinspection PyNestedDecorators
    @model_validator(mode="wrap")
    @classmethod
    def _from_image_data(cls, image: PILImageFile.ImageFile, handler: ModelWrapValidatorHandler[Self]) -> Self:
        if not isinstance(image, PILImageFile.ImageFile):
            return handler(image)

        try:
            obj = cls()
        except TypeError as ex:  # raised when trying to instantiate a models with missing abstract methods
            raise MusifyValueError(str(ex))

        obj.update_attributes(image)
        return obj

    # noinspection PyNestedDecorators
    @model_validator(mode="wrap")
    @classmethod
    def _from_image_bytes(cls, value: bytes | bytearray, handler: ModelWrapValidatorHandler[Self]) -> Self:
        if not isinstance(value, bytes | bytearray):
            return handler(value)

        img = Image.open(BytesIO(value))
        obj = handler(img)
        del img
        return obj

    # noinspection PyNestedDecorators
    @field_validator("type", mode="before")
    @classmethod
    def _get_type_from_number(cls, value: str | int) -> str:
        if not isinstance(value, int):
            return value

        # noinspection PyTypeChecker
        types = dict(zip(map(int, cls.__type_map.values()), cls.__type_map.keys()))
        if value not in types:
            raise MusifyValueError(
                f"Invalid picture type value: {value}. Valid values are: {", ".join(map(str, types))}"
            )

        return types[value]

    # noinspection PyNestedDecorators
    @field_validator("type", mode="after")
    @classmethod
    def _validate_id3_type(cls, value: str) -> str:
        if value not in cls.__type_map:
            raise MusifyValueError(f"Invalid ID3-tag type: {value}. Valid values are: {', '.join(cls.__type_map)}")
        return value

    def update_attributes(self, image: PILImageFile.ImageFile) -> None:
        """Update the image attributes based on the loaded image."""
        self.mime = Image.MIME[image.format]
        self.height = image.height
        self.width = image.width

    def __lt__(self, other):
        return isinstance(other, ImageBase) and self.height < other.height and self.width < other.width

    def __le__(self, other):
        return isinstance(other, ImageBase) and self.height <= other.height and self.width <= other.width

    def __gt__(self, other):
        return isinstance(other, ImageBase) and self.height > other.height and self.width > other.width

    def __ge__(self, other):
        return isinstance(other, ImageBase) and self.height >= other.height and self.width >= other.width


class ImageSource(ImageBase, metaclass=ABCMeta):
    @abstractmethod
    async def load(self, **kwargs) -> PILImageFile.ImageFile:
        """Load the image."""
        raise NotImplementedError


class ImageFile(ImageSource):
    """Represents an image file saved on a filesystem."""
    path: Path = Field(
        description="The path to the image file.",
    )

    def __str__(self) -> str:
        return str(self.path)

    def __eq__(self, other: Self) -> bool:
        if self is other:
            return True
        if not isinstance(other, self.__class__):
            return super().__eq__(other)
        return self.path == other.path and self.type == other.type

    async def load(self) -> PILImageFile.ImageFile:
        # TODO: improve async performance?
        async with aiofiles.open(self.path, mode='rb') as file:
            img = Image.open(BytesIO(await file.read()))
        return img


class FileEmbeddedImage(ImageSource, metaclass=ABCMeta):
    """Represents an embedded image of a file."""
    path: Path | None = Field(
        description="The path to the file containing the embedded image.",
        default=None,
    )

    def __eq__(self, other: Self) -> bool:
        if self is other:
            return True
        if not isinstance(other, self.__class__):
            return super().__eq__(other)
        return (self.path is None or self.path == other.path) and self.type == other.type


class ImageURL(ImageSource):
    """Represents an image link."""
    url: InstanceOf[URL] = Field(
        description="The URL of the image.",
    )

    # noinspection PyNestedDecorators
    @field_validator("url", mode="before", check_fields=True)
    @staticmethod
    def _cast_to_url(value: str) -> URL:
        if not isinstance(value, str):
            return value
        return URL(value)

    def __str__(self) -> str:
        return str(self.url)

    def __eq__(self, other: Self) -> bool:
        if self is other:
            return True
        if not isinstance(other, self.__class__):
            return super().__eq__(other)
        return self.url == other.url and self.type == other.type

    async def load(self, session: aiohttp.ClientSession = None, **__) -> PILImageFile.ImageFile:
        """Load the image from the URL."""
        close_session = False
        if session is None:
            close_session = True
            session = aiohttp.ClientSession()

        async with session.request(method=HTTPMethod.GET, url=self.url) as response:
            image_bytes = await response.read()

        if close_session:
            await session.close()

        return Image.open(BytesIO(image_bytes))


class HasImages(AttributeResource):
    """Represents a resource that has associated images."""
    images: MutableMapping[str, ImageFile | ImageURL | ImageSource] = Field(
        description="Images associated with this resource mapped to their type.",
        default_factory=dict,
    )

    async def load_images(self, update_attributes: bool = True, **kwargs) -> dict[str, PILImageFile.ImageFile]:
        """Return the stored images, loading any images from the URLs if available."""
        images: dict[str, PILImageFile.ImageFile] = {}
        for kind, image in self.images.items():
            img = await image.load(**kwargs)
            images[kind] = img
            if update_attributes:
                image.update_attributes(img)

        return images
