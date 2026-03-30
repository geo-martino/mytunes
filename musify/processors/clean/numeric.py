from collections.abc import Collection
from typing import Any

from pydantic import Field, NonNegativeInt, validate_call

from musify.models import AttributeModel
from musify.models.collection import CollectionModel
from musify.models.item.album import HasAlbum
from musify.models.properties.date import HasReleaseDate, SparseDate
from musify.models.properties.length import HasLength, Length
from musify.processors.clean._base import TagCleaner


class NumericCleaner[IT: AttributeModel](TagCleaner[IT, int | float]):
    round_to_nearest: NonNegativeInt = Field(
        description="Round the value to nearest integer.",
        default=0,
    )

    @classmethod
    def can_clean(cls, item: Any) -> bool:
        return item is None or isinstance(item, int | float)

    @validate_call
    def clean(self, item: int | float | IT | None) -> int | float:
        if item is None:
            return 0

        value = item if isinstance(item, int | float) else self._get_item_value(item)

        if self.round_to_nearest > 0:
            value = round(value / self.round_to_nearest) * self.round_to_nearest

        return value

    @classmethod
    def _get_item_value(cls, item: Any) -> int | float:
        match item:
            case int() | float():
                return item
            case None:
                return 0
            case _:
                return super()._get_item_value(item)


class LengthCleaner(NumericCleaner[HasLength]):
    @classmethod
    def can_clean(cls, item: Any) -> bool:
        match item:
            case Length():
                return True
            case HasLength():
                return cls.can_clean(item.length)
            case _:
                return super().can_clean(item)

    @classmethod
    def _get_item_value(cls, item: int | float | Length | HasLength | None) -> int | float:
        match item:
            case int() | float():
                length = item
            case Length():
                length = float(item)
            case HasLength():
                length = cls._get_item_value(item.length)
            case _:
                length = super()._get_item_value(item)

        return length


class ReleaseYearCleaner(NumericCleaner[HasAlbum | HasReleaseDate]):
    @classmethod
    def can_clean(cls, item: Any) -> bool:
        match item:
            case SparseDate():
                return super().can_clean(item.year)
            case HasReleaseDate():
                return cls.can_clean(item.released_at)
            case HasAlbum():
                return cls.can_clean(item.album)
            case _:
                return super().can_clean(item)

    @classmethod
    def _get_item_value(cls, item: SparseDate | HasAlbum | HasReleaseDate | None) -> int:
        match item:
            case SparseDate():
                year = item.year
            case HasReleaseDate():
                year = cls._get_item_value(item.released_at)
            case HasAlbum():
                year = cls._get_item_value(item.album)
            case _:
                year = super()._get_item_value(item)

        return year


class TotalItemsCleaner(NumericCleaner[CollectionModel]):
    @classmethod
    def can_clean(cls, item: Any) -> bool:
        match item:
            case CollectionModel():
                return super().can_clean(item.count)
            case _:
                return super().can_clean(item)

    @classmethod
    def _get_item_value(cls, item: CollectionModel | Collection | None) -> int:
        match item:
            case CollectionModel():
                total = item.count
            case Collection() as items if not isinstance(items, str):
                total = len(items)
            case _:
                total = super()._get_item_value(item)

        return total
