from pydantic import Field, AliasPath, PositiveInt

from musify.remote import RemoteModel


class HasFollowers(RemoteModel):
    followers: PositiveInt = Field(
        description="The number of followers for this item",
        validation_alias=AliasPath("followers", "total"),
    )
