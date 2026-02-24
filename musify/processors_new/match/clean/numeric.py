from abc import ABCMeta

from pydantic import Field, NonNegativeInt

from musify.models import AttributeModel
from musify.models.item.album import HasAlbum
from musify.models.properties.date import HasReleaseDate
from musify.models.properties.length import HasLength
from musify.processors_new.match.clean._base import TagCleaner


class NumericCleaner[I: AttributeModel](TagCleaner[I, int | float], metaclass=ABCMeta):
    round_to_nearest: NonNegativeInt = Field(
        description="Round the value to nearest integer.",
        default=0,
    )

    def clean(self, item: int | float | I | None) -> int | float:
        if item is None:
            return 0

        value = item if isinstance(item, int | float) else self._get_item_value(item)

        if self.round_to_nearest > 0:
            value = round(value / self.round_to_nearest) * self.round_to_nearest

        return value


class LengthCleaner(NumericCleaner[HasLength]):
    def _get_item_value(self, item: HasLength) -> float:
        if item is None or item.length is None:
            return 0
        return float(item.length)


class ReleaseYearCleaner(NumericCleaner[HasAlbum | HasReleaseDate]):
    def _get_item_value(self, item: HasAlbum | HasReleaseDate) -> int:
        if isinstance(item, HasAlbum):
            item = item.album

        if item is None or item.released_at is None:
            return 0
        return item.released_at.year
