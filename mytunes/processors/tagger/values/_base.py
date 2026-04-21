from abc import abstractmethod
from typing import Any, final, Literal, Annotated

from pydantic import Field, AliasChoices

from mytunes.processors.filters import Filter
from ...._base import BaseModel
from ...._base.discriminator import DiscriminatorModel, DiscriminatorAttribute
from ...._types import StrippedString


# noinspection PyAbstractClass
class Value[OT: str, IT: BaseModel, VT: Any](DiscriminatorModel):
    operation: Annotated[OT, DiscriminatorAttribute()] = Field(
        description="The name of this operation."
    )

    @abstractmethod
    def get(self, item: IT) -> VT:
        """Get the value of a tag from the item."""
        raise NotImplementedError


class HasCondition[VT: Any](BaseModel):
    condition: Filter | None = Field(
        description="The condition that the tag value should meet in order to be returned.",
        default=None,
        validation_alias=AliasChoices("condition", "when", "if")
    )

    def _check(self, value: VT) -> bool:
        return self.condition is None or not self.condition or self.condition.check(value)


@final
class FixedValue[VT: Any](Value[Literal["fixed"], BaseModel, VT]):
    """Always returns a fixed tag value."""
    __final__ = True

    field: StrippedString | None = Field(
        description="The name of the fixed value.",
        alias="name",
        default=None
    )
    value: VT = Field(
        description="The value of the fixed value.",
    )

    def get(self, item: Any) -> VT:
        return self.value


def from_fixed_value[T](value: T) -> T | FixedValue:
    """Validator to assign a set of fields to a FieldValue operation."""
    if not isinstance(value, str | int | float | bool | set | tuple | list):
        return value
    return FixedValue(value=value)
