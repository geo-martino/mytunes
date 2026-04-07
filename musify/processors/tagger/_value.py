from copy import copy
from pathlib import Path
from typing import Any, cast, final

from pydantic import Field, NonNegativeInt, PositiveInt, AliasChoices, validate_call, model_validator
from pydantic.fields import FieldInfo
from typing_inspection.typing_objects import is_typevar

from musify.processors._types import get_tag_fields_type
from musify.processors.filters import Filter
from ..._models import AttributeModel, ModelMetaclass, BaseModel
from ..._models.properties.file import IsLocalFile
from ..._models.properties.order import Position
from ..._types import StrippedString


class _HasCondition[VT: Any](BaseModel):
    condition: Filter | None = Field(
        description="The condition that the tag value should meet in order to be returned.",
        default=None,
        validation_alias=AliasChoices("condition", "when", "if")
    )

    def _check(self, value: VT) -> bool:
        return self.condition is None or not self.condition.ready or self.condition.check(value)


class FieldValueMetaclass(ModelMetaclass):
    def __new__(mcs, cls_name: str, bases: tuple[type[Any], ...], namespace: dict[str, Any], **kwargs: Any):
        # set appropriate field types from the generic type
        base = next((base for base in bases if isinstance(base, mcs) and issubclass(base, BaseModel)), None)
        generics = next((base.__pydantic_generic_metadata__["args"] for base in bases if isinstance(base, mcs)), None)
        if base is not None:
            info = base.model_fields.get("field")
            mcs._set_annotation_from_generic_type(info, generics)

        cls = cast('type[FieldValue]', super().__new__(mcs, cls_name, bases, namespace, **kwargs))

        return cls

    @classmethod
    def _set_annotation_from_generic_type(cls, info: FieldInfo, generics: list[type[AttributeModel]]) -> None:
        attribute_type = generics[1] if len(generics) > 1 else None
        if is_typevar(attribute_type):
            attribute_type = None
        info.annotation = get_tag_fields_type(attribute_type)


@final
class FieldValue[IT: AttributeModel, VT: Any](_HasCondition[VT], metaclass=FieldValueMetaclass):
    """Gets tag values according to some rules."""
    __final__ = True

    field: get_tag_fields_type() = Field(
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
class FixedValue[VT: Any](FieldValue[Any, VT]):
    """Always returns a fixed tag value."""
    __final__ = True

    field: StrippedString = Field(
        description="The name of the fixed value.",
        validation_alias="name",
    )
    value: VT = Field(
        description="The value of the fixed value.",
    )

    def get(self, *_, **__) -> VT:
        return self.value


@final
class PositionValue[IT: AttributeModel](FieldValue[IT, Position]):
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
class PathValue[IT: IsLocalFile](FieldValue[IT, Path]):
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
