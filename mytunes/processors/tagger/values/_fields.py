from collections.abc import Sequence
from copy import copy
from pathlib import Path
from typing import Any, final, Literal

from pydantic import Field, NonNegativeInt, PositiveInt, validate_call, model_validator
from typing_inspection.typing_objects import is_typevar

from mytunes.processors._types import get_tag_attributes_type, _ATTRIBUTE_FIELD_TYPE, ItemCollection
from mytunes.core.properties.file import IsLocalFile
from mytunes.core.properties.order import Position
from ._base import HasCondition, Value
from ...._base import BaseModel
from ...._base.attribute import AttributeModel
from ...._base.discriminator import DiscriminatorMetaclass


class FieldValueMetaclass(DiscriminatorMetaclass):
    def __new__(mcs, cls_name: str, bases: tuple[type[Any], ...], namespace: dict[str, Any], **kwargs: Any):
        # set appropriate field types from the generic type
        base = next((base for base in bases if isinstance(base, mcs) and issubclass(base, BaseModel)), None)
        generics = next((base.__pydantic_generic_metadata__["args"] for base in bases if isinstance(base, mcs)), None)
        info = base.model_fields.get("field") if base is not None else None
        if info is not None:
            info.annotation = mcs._get_readable_annotation_from_generic_type(generics)

        return super().__new__(mcs, cls_name, bases, namespace, **kwargs)

    @staticmethod
    def _get_readable_annotation_from_generic_type(generics: list[type[AttributeModel]]) -> Any:
        generic = generics[1] if len(generics) > 1 else None
        if is_typevar(generic):
            generic = None
        return get_tag_attributes_type(generic)


class _FieldValue[OT: str, IT: AttributeModel, VT: Any](
    Value[OT, IT, VT], HasCondition[VT], metaclass=FieldValueMetaclass
):
    """Gets tag values from another field on the same item."""

    field: _ATTRIBUTE_FIELD_TYPE = Field(
        description="The field from which to get a tag value from.",
    )

    @model_validator(mode="before")
    @classmethod
    def _from_field[T](cls, data: T | str) -> T | dict[str, Any]:
        if not isinstance(data, str):
            return data
        return dict(field=data)

    @validate_call
    def get(self, item: IT) -> VT | None:
        """Get the tag value from the given item if it meets the condition (if applicable)."""
        value = self._get(item)
        return value if self._check(value) else None

    def _get(self, item: IT) -> Any:
        return getattr(item, self.field)


@final
class FieldValue[IT: AttributeModel, VT: Any](_FieldValue[Literal["field"], IT, VT]):
    __final__ = True


def from_field_names[T](fields: T | Sequence[str]) -> T | list[FieldValue]:
    """Validator to assign a set of fields to a FieldValue operation."""
    if isinstance(fields, str):
        fields = [fields]
    if not isinstance(fields, ItemCollection):
        return fields
    return [FieldValue(field=field) if isinstance(field, str) else field for field in fields]


@final
class PositionValue[IT: AttributeModel](_FieldValue[Literal["position"], IT, Position]):
    """Gets a position tag according to some rules."""
    __final__ = True

    leading_zeros: bool | NonNegativeInt = Field(
        description="Whether leading zeros should be included in the tag value.",
        default=True,
    )

    @validate_call
    def get(self, item: IT) -> Position | None:
        value: Position = copy(self._get(item))
        if value is None:
            return value

        value.zero_fill = self.leading_zeros
        return value if self._check(value) else None


@final
class PathValue[IT: IsLocalFile](_FieldValue[Literal["path"], IT, Path]):
    """Gets a position tag according to some rules."""
    __final__ = True

    parent: PositiveInt | None = Field(
        description="Whether leading zeros should be included in the tag value.",
        default=None,
    )

    @validate_call
    def get(self, item: IT) -> Path | None:
        value: Path = copy(self._get(item))
        if value is None:
            return value

        if self.parent is not None:
            value = value.parts[-self.parent - 1]
        return value if self._check(value) else None


type FieldValueT = _FieldValue.annotation
