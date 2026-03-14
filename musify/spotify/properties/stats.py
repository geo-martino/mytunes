from pydantic import Field, NonNegativeInt, AliasPath

from musify.models import AttributeModel


class HasPopularity(AttributeModel):
    popularity: int | None = Field(
        description="The popularity of the item, between 0 and 100",
        default=None,
        ge=0,
        le=100,
    )


class HasFollowers(AttributeModel):
    followers: NonNegativeInt | None = Field(
        description="The number of followers for this item",
        default=None,
        validation_alias=AliasPath("followers", "total"),
    )
