from __future__ import annotations

from pydantic import PositiveFloat, Field

from musify.models import MusifyRootModel
from musify.models._base import AttributeResource


class Rating(MusifyRootModel[PositiveFloat]):
    def __hash__(self) -> int:
        return hash(self.root)


class HasRating(AttributeResource):
    """Represents a resource that has a rating."""
    rating: float | None = Field(
        description="The rating of this resource.",
        default=None,
    )
