from typing import ClassVar

from pydantic import Field, PositiveInt, EmailStr

from musify.models.properties.image import HasImages
from musify.models.properties.name import HasName
from musify.models.properties.uri import URI
from musify.remote._base import RemoteResource


class RemoteUser[UT: URI](RemoteResource[UT], HasName, HasImages):
    type: ClassVar[str] = "user"

    name: str = Field(
        description="The display name of the user",
    )
    email: EmailStr = Field(
        description="The email associated with the user",
    )
    followers: PositiveInt | None = Field(
        description="The number of followers of the user",
        default=None,
    )
