from abc import abstractmethod
from typing import Any, final

from pydantic import Field, AliasChoices

from mytunes.processors.filters import Filter
from ...._models import BaseModel
from ...._types import StrippedString


# noinspection PyAbstractClass
class Value[IT: BaseModel, VT: Any](BaseModel):
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
        return self.condition is None or not self.condition.ready or self.condition.check(value)


@final
class FixedValue[VT: Any](Value[BaseModel, VT]):
    """Always returns a fixed tag value."""
    __final__ = True

    field: StrippedString = Field(
        description="The name of the fixed value.",
        alias="name",
    )
    value: VT = Field(
        description="The value of the fixed value.",
    )

    def get(self, *_, **__) -> VT:
        return self.value
