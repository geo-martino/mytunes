from pydantic import Field, AliasPath, PositiveInt

from musify.models import AttributeModel


class HasFollowers(AttributeModel):
    followers: PositiveInt = Field(
        description="The number of followers for this item",
        validation_alias=AliasPath("followers", "total"),
    )
