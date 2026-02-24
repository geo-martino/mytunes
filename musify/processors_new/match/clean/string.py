import re
from abc import ABCMeta

from pydantic import Field

from musify.models import AttributeModel
from musify.models.item.album import HasAlbum
from musify.models.item.artist import HasArtists
from musify.models.properties.name import HasName
from musify.processors_new.match.clean._base import TagCleaner


class StringCleaner[I: AttributeModel](TagCleaner[I, str], metaclass=ABCMeta):
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

    def clean(self, item: str | I | None) -> str:
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


class NameCleaner(StringCleaner[HasName]):
    def _get_item_value(self, item: HasName | None) -> str:
        return item.name if item is not None else ""


class ArtistCleaner(StringCleaner[HasArtists]):
    def clean(self, item: HasArtists) -> list[str]:
        return [val for val in map(super().clean, item.artists) if val] if item is not None else []

    def _get_item_value(self, item: HasName | None) -> str:
        return item.name if item is not None else ""


class AlbumCleaner(StringCleaner[HasAlbum]):
    def _get_item_value(self, item: HasAlbum | None) -> str:
        if item is None or item.album is None:
            return ""
        return item.album.name
