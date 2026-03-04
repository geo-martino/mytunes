from pydantic import Field, AliasPath, PositiveInt

from musify.models import AttributeModel


class HasFollowers(AttributeModel):
    followers: PositiveInt | None = Field(
        description="The number of followers for this item",
        default=None,
        validation_alias=AliasPath("followers", "total"),
    )
