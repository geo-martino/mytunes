from abc import abstractmethod
from collections.abc import Sequence, Collection, Iterable
from typing import Any, Union

from pydantic import Field, PositiveInt

from musify.exception import MusifyValueError
from musify.processors.sort import ItemSorter
from musify.processors.tagger.values import Value, CollectionValue, HasCondition
from ._base import TaggerMetaclass
from .._types import _TAG_FIELD_TYPE
from ..._models import AttributeModel, BaseModel


# noinspection PyAbstractClass
class Setter[IT: AttributeModel, VT: Any](BaseModel, metaclass=TaggerMetaclass):
    """Sets tags on items according to some rules."""
    field: _TAG_FIELD_TYPE = Field(
        description="The field to set the tag value to.",
    )
    value: Value.annotation = Field(
        description="The value getter for the tag value to set.",
    )

    @abstractmethod
    def set(self, item: IT, other: Collection[IT] = ()) -> None:
        """Sets the configured tag to the item."""
        raise NotImplementedError


class ValueSetter[IT: AttributeModel, VT: Any](Setter[IT, VT]):
    def set(self, item: IT, other: Collection[IT] = ()) -> None:
        value = self.value.get(item)
        if value is None:
            return

        setattr(item, self.field, value)


class GroupedSetter[IT: AttributeModel, VT: Any](Setter[IT, VT]):
    value: CollectionValue.annotation = Field(
        description="The value getter for the tag value to set.",
    )
    group_by: Sequence[_TAG_FIELD_TYPE] = Field(
        description="The fields to group by.",
        default_factory=tuple,
    )

    def set(self, item: IT, other: Collection[IT] = ()) -> None:
        self._validate_item_in_group(item, other)

        group = self._group_items(item, other)

        value = self.value.get(group)
        if value is None:
            return

        setattr(item, self.field, value)

    @staticmethod
    def _validate_item_in_group(item: IT, other: Collection[IT] = ()) -> None:
        if item not in other:
            raise MusifyValueError("Given item must be present in the group.")

    def _group_items(self, item: IT, other: Collection[IT]) -> Iterable[IT]:
        if not self.group_by:
            return other

        def _is_in_group(it: IT) -> bool:
            return all(getattr(it, field, None) == getattr(item, field, None) for field in self.group_by)
        return filter(_is_in_group, other)


class SortedSetter[IT: AttributeModel, VT: Any](GroupedSetter[IT, VT]):
    sort_by: ItemSorter = Field(
        description="The fields to sort by.",
        default_factory=tuple,
    )

    def set(self, item: IT, other: Collection[IT] = ()) -> None:
        self._validate_item_in_group(item, other)

        group = list(self._group_items(item, other))
        self.sort_by.sort(group)

        value = self.value.get(group)
        if value is None:
            return

        setattr(item, self.field, value)


class IncrementalSetter[IT: AttributeModel](SortedSetter[IT, int], HasCondition[int]):
    # make optional
    value: Union[CollectionValue.annotation, None] = Field(
        description="The value getter for the tag value to set.",
        default=None,
    )
    start: PositiveInt = Field(
        description="The starting index value to assign to the item.",
        default=1,
    )
    increment: PositiveInt = Field(
        description="The amount to increment the value by.",
        default=1,
    )

    def set(self, item: IT, other: Collection[IT] = ()) -> None:
        self._validate_item_in_group(item, other)

        group = list(self._group_items(item, other))
        self.sort_by.sort(group)

        if self.value is not None:
            value = self.value.get(group)
            if value is None or not self._check(value):
                return

        value = self.start + (group.index(item) * self.increment)
        setattr(item, self.field, value)
