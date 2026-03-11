from __future__ import annotations

from pydantic import NonNegativeFloat, Field

from musify.models._base import RootModel, AttributeResource


class Rating(RootModel[NonNegativeFloat]):
    def __hash__(self) -> int:
        return hash(self.root)


class HasRating(AttributeResource):
    """Represents a resource that has a rating."""
    rating: float | None = Field(
        description="The rating of this resource.",
        default=None,
    )
