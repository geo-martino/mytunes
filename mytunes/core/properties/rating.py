from __future__ import annotations

from typing import Annotated

from aiorequestful.types import Number
from pydantic import NonNegativeFloat, Field

from ..._base.attribute import AttributeModel, Attribute
from mytunes.core.properties import NumberModel


class Rating[T: Number](NumberModel[T]):
    pass


class HasRating(AttributeModel):
    """Represents a resource that has a rating."""
    rating: Annotated[Rating[NonNegativeFloat] | None, Attribute()] = Field(
        description="The rating of this resource.",
        default=None,
    )
