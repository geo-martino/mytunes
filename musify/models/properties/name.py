from __future__ import annotations

from typing import Any, Self

from pydantic import Field, model_validator

from musify._types import StrippedString
from musify.models._base import _AttributeModel


class HasName(_AttributeModel):
    name: StrippedString = Field(
        description="The name of this resource."
    )

    # noinspection PyNestedDecorators
    @model_validator(mode="before")
    @staticmethod
    def _from_name[T](value: T) -> T | dict[str, Any]:
        if not isinstance(value, str):
            return value
        return dict(name=value)

    def __lt__(self, other: Self):
        return self.name < other.name

    def __le__(self, other: Self):
        return self.name <= other.name

    def __gt__(self, other: Self):
        return self.name > other.name

    def __ge__(self, other: Self):
        return self.name >= other.name
