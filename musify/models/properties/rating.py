from __future__ import annotations

from pydantic import NonNegativeFloat, Field

from musify.models._base import AttributeResource
from musify.models.properties import NumberModel


class Rating[T: int | float](NumberModel[T]):
    pass


class HasRating(AttributeResource):
    """Represents a resource that has a rating."""
    rating: Rating[NonNegativeFloat] | None = Field(
        description="The rating of this resource.",
        default=None,
    )
