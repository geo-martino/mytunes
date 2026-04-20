from abc import abstractmethod
from collections.abc import Sequence, Collection, Iterable
from typing import Any, Union

from pydantic import Field, PositiveInt
from typing_inspection.typing_objects import is_typevar

from mytunes.exception import MyTunesValueError
from mytunes.processors.sort import ItemSorter
from mytunes.processors.tagger._types import _WRITEABLE_ATTRIBUTE_FIELD_TYPE, get_writeable_tag_attributes_type
from mytunes.processors.tagger.values import Value, CollectionValue, HasCondition
from .._types import _ATTRIBUTE_FIELD_TYPE
from ..._base import BaseModel, ModelMetaclass
from ..._base.attribute import AttributeModel


class SetterMetaclass(ModelMetaclass):
    def __new__(mcs, cls_name: str, bases: tuple[type[Any], ...], namespace: dict[str, Any], **kwargs: Any):
        # set appropriate field types from the generic type
        base = next((base for base in bases if isinstance(base, mcs) and issubclass(base, BaseModel)), None)
        generics = next((base.__pydantic_generic_metadata__["args"] for base in bases if isinstance(base, mcs)), None)

        info = base.model_fields.get("field") if base is not None else None
        if info is not None:
            info.annotation = mcs._get_writeable_annotation_from_generic_type(generics)

        return super().__new__(mcs, cls_name, bases, namespace, **kwargs)

    @staticmethod
    def _get_writeable_annotation_from_generic_type(generics: list[type[AttributeModel]]) -> Any:
        generic = generics[1] if len(generics) > 1 else None
        if is_typevar(generic):
            generic = None
        return get_writeable_tag_attributes_type(generic)


# noinspection PyAbstractClass
class Setter[IT: AttributeModel, VT: Any](BaseModel, metaclass=SetterMetaclass):
    """Sets tags on items according to some rules."""
    field: _WRITEABLE_ATTRIBUTE_FIELD_TYPE = Field(
        description="The field to set the tag value to.",
    )
    value: Value.annotation = Field(
        description="The value getter for the tag value to set.",
    )

    @abstractmethod
    def set(self, item: IT, other: Collection[IT] = ()) -> bool:
        """Sets the configured tag to the item. Returns True if the tag was set."""
        raise NotImplementedError


class ValueSetter[IT: AttributeModel, VT: Any](Setter[IT, VT]):
    def set(self, item: IT, other: Collection[IT] = ()) -> bool:
        value = self.value.get(item)
        if value is None:
            return False
        if getattr(item, self.field) == value:
            return False

        setattr(item, self.field, value)
        return True


class GroupedSetter[IT: AttributeModel, VT: Any](Setter[IT, VT]):
    value: CollectionValue.annotation = Field(
        description="The value getter for the tag value to set.",
    )
    group_by: Sequence[_ATTRIBUTE_FIELD_TYPE] = Field(
        description="The fields to group by.",
        default_factory=tuple,
    )

    def set(self, item: IT, other: Collection[IT] = ()) -> bool:
        self._validate_item_in_group(item, other)

        group = self._group_items(item, other)

        value = self.value.get(group)
        if value is None:
            return False
        if getattr(item, self.field) == value:
            return False

        setattr(item, self.field, value)
        return True

    @staticmethod
    def _validate_item_in_group(item: IT, other: Collection[IT] = ()) -> None:
        if item not in other:
            raise MyTunesValueError("Given item must be present in the group.")

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

    def set(self, item: IT, other: Collection[IT] = ()) -> bool:
        self._validate_item_in_group(item, other)

        group = list(self._group_items(item, other))
        self.sort_by.sort(group)

        value = self.value.get(group)
        if value is None:
            return False
        if getattr(item, self.field) == value:
            return False

        setattr(item, self.field, value)
        return True


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

    def set(self, item: IT, other: Collection[IT] = ()) -> bool:
        self._validate_item_in_group(item, other)

        group = list(self._group_items(item, other))
        self.sort_by.sort(group)

        if self.value is not None:
            value = self.value.get(group)
            if value is None or not self._check(value):
                return False

        value = self.start + (group.index(item) * self.increment)
        if getattr(item, self.field) == value:
            return False

        setattr(item, self.field, value)
        return True
