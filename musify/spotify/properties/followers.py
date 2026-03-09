from pydantic import Field, AliasPath, NonNegativeInt

from musify.models import AttributeModel


class HasFollowers(AttributeModel):
    followers: NonNegativeInt | None = Field(
        description="The number of followers for this item",
        default=None,
        validation_alias=AliasPath("followers", "total"),
    )
