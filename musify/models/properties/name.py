from __future__ import annotations

from typing import Self

from pydantic import Field, model_validator, ModelWrapValidatorHandler

from musify._types import StrippedString
from musify.models._base import _AttributeModel


class HasName(_AttributeModel):
    name: StrippedString = Field(
        description="The name of this resource."
    )

    # noinspection PyNestedDecorators
    @model_validator(mode="wrap")
    @staticmethod
    def _from_name(value: str, handler: ModelWrapValidatorHandler[Self]) -> Self:
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


HasName.__tag_fields__ = frozenset({*HasName.model_fields})
