from typing import ClassVar

from pydantic import Field, EmailStr

from musify._types import StrippedString
from musify.models.properties.image import HasImages
from musify.models.properties.name import HasName
from musify.models.properties.uri import URI
from musify.remote._base import RemoteResource


class RemoteUser[UT: URI](RemoteResource[UT], HasName, HasImages):
    type: ClassVar[str] = "user"

    name: StrippedString = Field(
        description="The display name of the user",
    )
    email: EmailStr | None = Field(
        description="The email associated with the user",
        default=None,
    )
