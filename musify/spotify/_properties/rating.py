from typing import Annotated

from pydantic import Field

from musify.models.metadata import Attribute
from musify.models.properties.rating import HasRating, Rating


class HasSpotifyRating(HasRating):
    rating: Annotated[Rating[int] | None, Attribute()] = Field(
        description="The popularity of the item, between 0 and 100",
        default=None,
        validation_alias="popularity",
        ge=0,
        le=100,
    )
