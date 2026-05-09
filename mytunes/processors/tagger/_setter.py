from abc import abstractmethod
from collections import defaultdict
from collections.abc import Sequence, Collection, Iterable, Hashable, Mapping
from typing import Any, Union, final, Annotated, Literal, Self

from pydantic import Field, PositiveInt, BeforeValidator, PrivateAttr, model_validator
from typing_inspection.typing_objects import is_typevar

from mytunes.exception import MyTunesValueError, MyTunesAttributeError
from mytunes.processors.sort import ItemSorter
from mytunes.processors.tagger._types import _WRITEABLE_ATTRIBUTE_FIELD_TYPE, get_writeable_tag_attributes_type
from mytunes.processors.tagger.values import Value, AggregateValue, HasCondition
from mytunes.processors.tagger.values import from_fixed_value
from .._types import _ATTRIBUTE_FIELD_TYPE
from ..._base import BaseModel
from ..._base.attribute import AttributeModel
from ..._base.discriminator import DiscriminatorMetaclass, DiscriminatorAttribute, DiscriminatorModel
from ..._types import TO_TUPLE


class SetterMetaclass(DiscriminatorMetaclass):
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
class Setter[OT: str, IT: AttributeModel, VT: Any](DiscriminatorModel, metaclass=SetterMetaclass):
    """Sets tags on items according to some rules."""
    operation: Annotated[OT, DiscriminatorAttribute()] = Field(
        description="The name of this operation."
    )

    field: _WRITEABLE_ATTRIBUTE_FIELD_TYPE = Field(
        description="The field to set the tag value to.",
    )
    value: Annotated[Value.annotation, BeforeValidator(from_fixed_value)] = Field(
        description="The value getter for the tag value to set.",
    )

    _items: Collection[IT] = PrivateAttr(
        # description="The items in the collection used in various ways by value getters/setters."
        default_factory=tuple,
    )

    def get(self, item: IT) -> VT:
        """Get the value for the given item."""
        return self.value.get(self._items) if isinstance(self.value, AggregateValue) else self.value.get(item)

    @abstractmethod
    def set(self, item: IT) -> bool:
        """Sets the configured tag to the item. Returns True if the tag was set."""
        raise NotImplementedError

    @classmethod
    def _set_attribute(cls, item: IT, field: str, value: Any):
        try:
            setattr(item, field, value)
        except MyTunesAttributeError:
            # handle cases where model can be set by a single value e.g. HasName
            parent_field = ".".join(field.split(".")[:-1])
            if parent_field == field:
                raise
            cls._set_attribute(item, parent_field, value)

    def set_context(self, items: Iterable[IT] = ()) -> None:
        """
        Set the collection of items which contain all items to be set.
        Used by various setters to assign tags based on collection values.
        """
        self._items = tuple(items)

    def clear_context(self) -> None:
        """Clear the collection of items."""
        self._items = tuple()


@final
class ValueSetter[IT: AttributeModel, VT: Any](Setter[Literal["value"], IT, VT]):
    __final__ = True

    def set(self, item: IT) -> bool:
        value = self.get(item)

        if value is None:
            return False
        if getattr(item, self.field) == value:
            return False

        self._set_attribute(item, self.field, value)
        return True


class _GroupSetter[OT: str, IT: AttributeModel, VT: Any](Setter[OT, IT, VT]):
    value: AggregateValue.annotation = Field(
        description="The value getter for the tag value to set.",
    )
    group_by: Annotated[Sequence[_ATTRIBUTE_FIELD_TYPE], TO_TUPLE] = Field(
        description="The fields to group by.",
        default_factory=tuple,
    )

    _groups: Mapping[tuple[Hashable | None, ...], tuple[IT, ...]] = PrivateAttr(
        # description="The groups of items set in the context."
        default_factory=dict,
    )

    @model_validator(mode="after")
    def _set_groups(self) -> Self:
        self.set_context(self._items)
        return self

    def get(self, item: IT) -> VT:
        group = self._get_group(item)
        return self.value.get(group)

    def _get_group(self, item: IT) -> tuple[VT, ...]:
        values = tuple(getattr(item, field, None) for field in self.group_by)

        group = self._groups.get(tuple(values))
        if group is None:
            raise MyTunesValueError("Given item must be present in the currently set items.")

        return group

    def set(self, item: IT) -> bool:
        value = self.get(item)

        if value is None:
            return False
        if getattr(item, self.field) == value:
            return False

        self._set_attribute(item, self.field, value)
        return True

    def set_context(self, items: Iterable[IT] = ()) -> None:
        super().set_context(items)

        group_values: dict[tuple[Hashable | None, ...], list[IT]] = defaultdict(list)
        for item in items:
            values = [getattr(item, field, None) for field in self.group_by]
            group_values[tuple(values)].append(item)

        self._groups = {k: tuple(v) for k, v in group_values.items()}

    def clear_context(self) -> None:
        super().clear_context()
        self._groups = {}


@final
class GroupSetter[OT: str, IT: AttributeModel, VT: Any](_GroupSetter[Literal["group"], IT, VT]):
    __final__ = True


class _SortSetter[OT: str, IT: AttributeModel, VT: Any](_GroupSetter[OT, IT, VT]):
    sort_by: ItemSorter = Field(
        description="The fields to sort by.",
        default_factory=tuple,
    )

    def _get_group(self, item: IT) -> tuple[VT, ...]:
        group = list(super()._get_group(item))
        self.sort_by.sort(group)
        return tuple(group)


@final
class SortSetter[IT: AttributeModel, VT: Any](_SortSetter[Literal["sort"], IT, VT]):
    __final__ = True


@final
class IncrementalSetter[IT: AttributeModel](_SortSetter[Literal["incremental"], IT, int], HasCondition[int]):
    __final__ = True

    # now optional
    value: Union[AggregateValue.annotation, None] = Field(
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

    def get(self, item: IT) -> int | None:
        group = self._get_group(item)

        if self.value is not None:
            value = self.value.get(group)
            if value is None or not self._check(value):
                return None

        return self.start + (group.index(item) * self.increment)
