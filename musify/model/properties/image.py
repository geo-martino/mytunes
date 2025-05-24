from __future__ import annotations

import asyncio
from collections.abc import Sequence, MutableMapping, Mapping
from http import HTTPMethod
from io import BytesIO
from typing import Any, Self

import aiohttp
import mutagen.id3
from PIL import Image
from pydantic import InstanceOf, Field, PositiveInt, field_validator, field_serializer
from yarl import URL

from musify.exception import MusifyValueError
from musify.model import MusifyModel
from musify.model._base import _AttributeModel


class ImageLink(MusifyModel):
    """Represents an image link."""
    url: InstanceOf[URL] = Field(
        description="The URL of the image.",
    )
    height: PositiveInt | None = Field(
        description="The height of the image in pixels.",
        default=None,
    )
    width: PositiveInt | None = Field(
        description="The width of the image in pixels.",
        default=None,
    )

    # noinspection PyNestedDecorators
    @field_validator("url", mode="before", check_fields=True)
    @staticmethod
    def _cast_to_url(value: str) -> Any:
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
        return self.url == other.url

    def __ne__(self, other):
        return not self.__eq__(other)

    def __lt__(self, other):
        return isinstance(other, self.__class__) and self.height < other.height and self.width < other.width

    def __le__(self, other):
        return isinstance(other, self.__class__) and self.height <= other.height and self.width <= other.width

    def __gt__(self, other):
        return isinstance(other, self.__class__) and self.height > other.height and self.width > other.width

    def __ge__(self, other):
        return isinstance(other, self.__class__) and self.height >= other.height and self.width >= other.width

    async def load(self, session: aiohttp.ClientSession = None) -> Image:
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


class HasImages(_AttributeModel):
    """Represents a resource that has associated images."""
    images: MutableMapping[str, InstanceOf[Image.Image] | ImageLink] = Field(
        description="Images associated with this resource mapped to their type.",
        default_factory=dict,
    )

    # noinspection PyNestedDecorators
    @field_validator("images", mode="before")
    @staticmethod
    def _deserialize_images_from_bytes[T](data: T) -> T | dict[str | int, Image.Image]:
        if isinstance(data, bytes | bytearray):
            data = {get_picture_name_from_id3_value(mutagen.id3.PictureType.COVER_FRONT): data}
        if not isinstance(data, Mapping):
            return data

        return {
            kind: Image.open(BytesIO(img)) if isinstance(img, bytes | bytearray) else img
            for kind, img in data.items()
        }

    # noinspection PyNestedDecorators
    @field_validator("images", mode="before")
    @staticmethod
    def _convert_id3_value_to_picture_type_name[T](data: T) -> T | dict[str, Image.Image]:
        if not isinstance(data, Mapping):
            return data

        return {
            get_picture_name_from_id3_value(kind): img
            for kind, img in data.items()
        }

    # noinspection PyNestedDecorators
    @field_serializer("images", mode="plain", when_used="unless-none")
    def _serialize_images(
            self, images: MutableMapping[str, InstanceOf[Image.Image] | ImageLink]
    ) -> dict[str, bytes]:
        data: dict[str, bytes] = {}
        for kind, img in self.load_images().items():
            img_bytes = BytesIO()
            img.save(img_bytes, format=img.format)
            img_bytes = img_bytes.getvalue()
            data[kind] = img_bytes

        return data

    def load_images(self) -> dict[str, Image.Image]:
        """Return the stored images, loading any images from the URLs if available."""
        images: dict[str, Image.Image] = {}
        for kind, img in self.images.items():
            if isinstance(img, ImageLink):
                loop = asyncio.get_event_loop()
                img = loop.run_until_complete(img.load())

            images[kind] = img

        return images


# noinspection PyTypeChecker
PICTURE_TYPES = {
    name: int(enum) for name, enum in vars(mutagen.id3.PictureType).items()
    if isinstance(enum, mutagen.id3.PictureType)
}


def get_picture_name_from_id3_value(value: str | int) -> str:
    """Get the name of the picture type from its ID3 tag value."""
    if isinstance(value, str) and value.upper().replace(" ", "_") in PICTURE_TYPES:
        return value

    types = dict(zip(PICTURE_TYPES.values(), PICTURE_TYPES.keys()))
    if value not in types:
        raise MusifyValueError(f"Invalid picture type value: {value}. Valid values are: {", ".join(map(str, types))}")

    return types[value].replace("_", " ").title()


def get_picture_id3_value_from_name(name: str | int) -> int:
    """Get the name of the picture ID3 tag value from its name."""
    if isinstance(name, int) and name in PICTURE_TYPES.values():
        return name

    name = str(name).upper().replace(" ", "_")
    if name not in PICTURE_TYPES:
        raise MusifyValueError(f"Invalid picture type name: {name}. Valid names are: {", ".join(PICTURE_TYPES)}")

    return PICTURE_TYPES[name]
