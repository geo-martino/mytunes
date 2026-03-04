from pydantic import Field, PositiveInt

from musify.remote import RemoteModel


class HasPopularity(RemoteModel):
    popularity: int = Field(
        description="The popularity of the item, between 0 and 100",
        ge=0,
        le=100,
    )
