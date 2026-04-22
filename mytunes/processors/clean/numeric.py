from collections.abc import Collection
from typing import Any

from pydantic import Field, NonNegativeInt, validate_call

from mytunes._types import Number
from mytunes.core.album import HasAlbum
from mytunes.core.collection import CollectionModel
from mytunes.core.properties.date import HasReleaseDate, SparseDate
from mytunes.core.properties.length import HasLength, Length
from mytunes.processors.clean._base import TagCleaner
from ..._base.attribute import AttributeModel


class NumericCleaner[IT: AttributeModel](TagCleaner[IT, Number]):
    round_to_nearest: NonNegativeInt = Field(
        description="Round the value to nearest integer.",
        default=0,
    )

    @classmethod
    def can_clean(cls, item: Any, skip_on_exact_type: bool = False) -> bool:
        return isinstance(item, int | float)

    @validate_call
    def clean(self, item: Number | IT | None) -> Number:
        if item is None:
            return 0

        value = item if isinstance(item, int | float) else self._get_item_value(item)

        if self.round_to_nearest > 0:
            value = round(value / self.round_to_nearest) * self.round_to_nearest

        return value

    @classmethod
    def _get_item_value(cls, item: Any) -> Number:
        match item:
            case int() | float():
                return item
            case None:
                return 0
            case _:
                return super()._get_item_value(item)


class LengthCleaner(NumericCleaner[HasLength]):
    @classmethod
    def can_clean(cls, item: Any, skip_on_exact_type: bool = False) -> bool:
        match item:
            case Length() if skip_on_exact_type:
                return False
            case Length():
                return True
            case HasLength():
                return cls.can_clean(item.length)
            case _:
                return super().can_clean(item)

    @classmethod
    def _get_item_value(cls, item: Number | Length | HasLength | None) -> Number:
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
    def can_clean(cls, item: Any, skip_on_exact_type: bool = False) -> bool:
        match item:
            case SparseDate() if skip_on_exact_type:
                return False
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
    def can_clean(cls, item: Any, skip_on_exact_type: bool = False) -> bool:
        match item:
            case CollectionModel():
                return super().can_clean(item.total)
            case _:
                return super().can_clean(item)

    @classmethod
    def _get_item_value(cls, item: CollectionModel | Collection | None) -> int:
        match item:
            case CollectionModel():
                total = item.total
            case Collection() as items if not isinstance(items, str):
                total = len(items)
            case _:
                total = super()._get_item_value(item)

        return total
