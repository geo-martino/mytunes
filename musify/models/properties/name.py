from __future__ import annotations

from typing import Self, Annotated

from pydantic import Field, model_validator, ModelWrapValidatorHandler

from musify._types import StrippedString
from musify.models._attribute import AttributeModel
from musify.models._metadata import Attribute


class HasName(AttributeModel):
    name: Annotated[StrippedString, Attribute()] = Field(
        description="The name of this resource."
    )

    # noinspection PyNestedDecorators
    @model_validator(mode="wrap")
    @classmethod
    def _from_name(cls, value: str, handler: ModelWrapValidatorHandler[Self]) -> Self:
        if not isinstance(value, str):
            return handler(value)

        data = dict(name=value)
        return handler(data)

    def __lt__(self, other: Self):
        return self.name < other.name

    def __le__(self, other: Self):
        return self.name <= other.name

    def __gt__(self, other: Self):
        return self.name > other.name

    def __ge__(self, other: Self):
        return self.name >= other.name
