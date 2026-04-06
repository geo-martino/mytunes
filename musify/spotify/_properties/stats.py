from typing import Annotated

from pydantic import Field, NonNegativeInt, AliasPath

from ..._models import AttributeModel
from ..._models.metadata import Attribute


class HasFollowers(AttributeModel):
    followers: Annotated[NonNegativeInt | None, Attribute()] = Field(
        description="The number of followers for this item",
        default=None,
        validation_alias=AliasPath("followers", "total"),
    )
