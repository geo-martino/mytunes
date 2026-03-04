from pydantic import Field

from musify.models import AttributeModel


class HasPopularity(AttributeModel):
    popularity: int | None = Field(
        description="The popularity of the item, between 0 and 100",
        default=None,
        ge=0,
        le=100,
    )
