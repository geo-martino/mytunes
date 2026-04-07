from copy import copy
from pathlib import Path
from typing import Any, final

from pydantic import Field, NonNegativeInt, PositiveInt, validate_call, model_validator

from musify.processors._types import _TAG_FIELD_TYPE
from ._base import HasCondition, Value
from .._base import TaggerMetaclass
from ...._models import AttributeModel
from ...._models.properties.file import IsLocalFile
from ...._models.properties.order import Position


@final
class FieldValue[IT: AttributeModel, VT: Any](Value[IT, VT], HasCondition[VT], metaclass=TaggerMetaclass):
    """Gets tag values according to some rules."""
    __final__ = True

    field: _TAG_FIELD_TYPE = Field(
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
