from __future__ import annotations

from abc import abstractmethod
from collections.abc import Mapping, MutableMapping
from http import HTTPMethod
from inspect import isabstract
from io import BytesIO
from pathlib import Path
from typing import Self, ClassVar, Any, Annotated

import aiofiles
import aiohttp
import mutagen.id3
from PIL import Image, ImageFile as PILImageFile
from pydantic import Field, PositiveInt, field_validator, model_validator
from pydantic.functional_validators import ModelWrapValidatorHandler

from musify._types import StrippedString, UpperSnakeCase
from musify.models._attribute import AttributeModel
from musify.models._base import BaseModel
from musify.models.exception import MusifyValidationError
from musify.models.metadata import Attribute
from musify.models.properties.file import IsLocalFile
from musify.models.url import HttpURL


class ImageBase(BaseModel):
    """Represents an image."""
    # noinspection PyTypeChecker
    __type_map: ClassVar[Mapping[str, mutagen.id3.PictureType]] = {
        name: enum for name, enum in vars(mutagen.id3.PictureType).items()
        if isinstance(enum, mutagen.id3.PictureType)
    }

    type: Annotated[UpperSnakeCase, Attribute()] = Field(
        description="The type of the image, as defined by ID3 tags.",
        default="COVER_FRONT",
    )
    mime: Annotated[StrippedString | None, Attribute()] = Field(
        description="The MIME type of the image.",
        default=None,
    )
    description: Annotated[StrippedString | None, Attribute()] = Field(
        description="A description of the image.",
        default=None,
    )
    height: Annotated[PositiveInt | None, Attribute()] = Field(
        description="The height of the image in pixels.",
        default=None,
    )
    width: Annotated[PositiveInt | None, Attribute()] = Field(
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

        obj = cls()
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
            raise MusifyValidationError(
                f"Invalid picture type value: {value}. Valid values are: {", ".join(map(str, types))}"
            )

        return types[value]

    # noinspection PyNestedDecorators
    @field_validator("type", mode="after")
    @classmethod
    def _validate_id3_type(cls, value: str) -> str:
        if value not in cls.__type_map:
            raise MusifyValidationError(
                f"Invalid ID3-tag type: {value}. Valid values are: {', '.join(cls.__type_map)}"
            )
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


# noinspection PyAbstractClass
class ImageSource(ImageBase):
    @abstractmethod
    async def load(self, **kwargs) -> PILImageFile.ImageFile:
        """Load the image."""
        raise NotImplementedError


class ImageFile(ImageSource, IsLocalFile):
    """Represents an image file saved on a filesystem."""
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


# noinspection PyAbstractClass
class FileEmbeddedImage(ImageSource):
    """Represents an embedded image of a file."""
    path: Annotated[Path | None, Attribute()] = Field(
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
    url: Annotated[HttpURL, Attribute()] = Field(
        description="The URL of the image.",
    )

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


class HasImages(AttributeModel):
    """Represents a resource that has associated images."""
    images: Annotated[MutableMapping[str, ImageFile | ImageURL], Attribute()] = Field(
        description="Images associated with this resource mapped to their type.",
        default_factory=dict,
    )

    @field_validator("images", mode="before", check_fields=True)
    @classmethod
    def _from_none[T](cls, images: T | None) -> T | dict[str, Any]:
        return images if images is not None else {}

    @field_validator("images", mode="before", check_fields=True)
    @classmethod
    def _restructure_image_sequence[T](cls, images: T | list[dict]) -> T | dict[str, Any]:
        if not isinstance(images, list):
            return images

        images.sort(key=lambda i: i["height"], reverse=False)
        default_type = ImageBase.model_fields["type"].default
        return {image.get("type", default_type): image for image in images}

    async def load_images(self, update_attributes: bool = True, **kwargs) -> dict[str, PILImageFile.ImageFile]:
        """Return the stored images, loading any images from the URLs if available."""
        images: dict[str, PILImageFile.ImageFile] = {}
        for kind, image in self.images.items():
            img = await image.load(**kwargs)
            images[kind] = img
            if update_attributes:
                image.update_attributes(img)

        return images
