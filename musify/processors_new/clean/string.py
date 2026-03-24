import re
from collections.abc import Sequence
from typing import Any

from pydantic import Field, validate_call

from musify.exception import MusifyValueError, MusifyTypeError
from musify.models import AttributeModel
from musify.models.item.album import HasAlbum, Album
from musify.models.item.artist import HasArtists, Artist
from musify.models.properties.name import HasName
from musify.processors_new.clean._base import TagCleaner


class StringCleaner[IT: AttributeModel](TagCleaner[IT, str]):
    split_on: set[str] = Field(
        description=(
            "A set of phrases for which the cleaner will slice the tag value on and remove anything that comes after. "
            "This always happens first, before all other cleaning operations."
        ),
        default_factory=set,
    )
    drop_brackets: bool = Field(
        description="Whether to remove any text contained in brackets or parentheses.",
        default=True,
    )
    drop_non_alphanumeric: bool = Field(
        description="Whether to remove any non-alphanumeric characters.",
        default=True,
    )
    drop_phrases: set[str] = Field(
        description=(
            "A set of phrases to remove from this tag value. "
            "The cleaner will only remove whole words that match these phrases. "
            "This always happens last, after all other cleaning operations."
        ),
        default_factory=set,
    )

    @classmethod
    def can_clean(cls, item: Any) -> bool:
        return item is None or isinstance(item, str)

    @validate_call
    def clean(self, item: str | IT | None) -> str:
        if item is None:
            return ""

        value = item if isinstance(item, str) else self._get_item_value(item)
        value = value.casefold()

        for phrase in self.split_on:
            value = value.split(phrase)[0].rstrip()

        if self.drop_brackets:
            value = re.sub(r"[(\[].*?[)\]]", "", value).strip()

        if self.drop_non_alphanumeric:
            value = re.sub(r"[^\w']+", " ", value).strip()

        for phrase in self.drop_phrases:
            value = re.sub(rf"\s*\b{phrase}\b\s*", " ", value).strip()

        return value.strip()

    @classmethod
    def _get_item_value(cls, item: Any) -> str:
        match item:
            case str():
                return item
            case None:
                return ""
            case _:
                return super()._get_item_value(item)


class NameCleaner(StringCleaner[HasName]):
    @classmethod
    def can_clean(cls, item: Any) -> bool:
        match item:
            case HasName():
                return super().can_clean(item.name)
            case _:
                return super().can_clean(item)

    @classmethod
    def _get_item_value(cls, item: str | HasName | None) -> str:
        match item:
            case HasName():
                return item.name
            case _:
                return super()._get_item_value(item)


class ArtistCleaner(StringCleaner[HasArtists]):
    @classmethod
    def can_clean(cls, item: Any) -> bool:
        match item:
            case Artist():
                return super().can_clean(item.name)
            case HasArtists():
                return cls.can_clean(item.artists)
            case list():
                return all(cls.can_clean(it) for it in item)
            case _:
                return super().can_clean(item)

    @validate_call
    def clean(self, item: str | Sequence[str] | Artist | Sequence[Artist] | HasArtists) -> list[str]:
        match item:
            case str() | Artist():
                artists = [item]
            case HasArtists():
                artists = item.artists
            case Sequence():
                artists = item
            case _ if not self.can_clean(item):
                raise MusifyTypeError(f"Cannot clean item of type {type(item)} with {self.__class__.__name__}")

        return [val for val in map(super().clean, artists) if val]

    @classmethod
    def _get_item_value(cls, item: str | Artist | None) -> str:
        match item:
            case Artist():
                return item.name
            case _:
                return super()._get_item_value(item)


class AlbumCleaner(StringCleaner[HasAlbum]):
    @classmethod
    def can_clean(cls, item: Any) -> bool:
        match item:
            case Album():
                return super().can_clean(item.name)
            case HasAlbum():
                return cls.can_clean(item.album)
            case _:
                return super().can_clean(item)

    @classmethod
    def _get_item_value(cls, item: str | Album | HasAlbum | None) -> str:
        match item:
            case Album():
                return item.name
            case HasAlbum():
                return cls._get_item_value(item.album)
            case _:
                return super()._get_item_value(item)
