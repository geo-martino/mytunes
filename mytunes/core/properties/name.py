from __future__ import annotations

from typing import Self, Annotated, Any

from pydantic import Field, model_validator

from mytunes._types import StrippedString
from ..._base.attribute import AttributeModel, Attribute


class HasName(AttributeModel):
    name: Annotated[StrippedString, Attribute()] = Field(
        description="The name of this resource."
    )

    @model_validator(mode="before")
    @classmethod
    def _from_name[T](cls, data: T | str) -> T | dict[str, Any]:
        if not isinstance(data, str):
            return data

        return dict(name=data)

    def __lt__(self, other: Self):
        return self.name < other.name

    def __le__(self, other: Self):
        return self.name <= other.name

    def __gt__(self, other: Self):
        return self.name > other.name

    def __ge__(self, other: Self):
        return self.name >= other.name
