from typing import ClassVar, TYPE_CHECKING, Self

from pydantic import Field, EmailStr

from musify._types import StrippedString
from musify.models.properties.image import HasImages
from musify.models.properties.name import HasName
from musify.models.properties.uri import URI
from musify.models.remote import RemoteResource

if TYPE_CHECKING:
    from musify.models.api.user import HasUserEndpoints, UserEndpoints


class RemoteUser[UT: URI](RemoteResource[UT], HasName, HasImages):
    type: ClassVar[str] = "user"

    name: StrippedString = Field(
        description="The display name of the user",
    )
    email: EmailStr | None = Field(
        description="The email associated with the user",
        default=None,
    )

    def reload(self, api: HasUserEndpoints[UserEndpoints]) -> Self:
        return api.users.get_me()
