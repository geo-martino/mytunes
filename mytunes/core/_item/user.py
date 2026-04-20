from typing import ClassVar, TYPE_CHECKING, Self

from pydantic import Field, EmailStr

from mytunes.core.remote import RemoteResource
from mytunes._types import StrippedString
from mytunes.properties.image import HasImages
from mytunes.properties.name import HasName
from mytunes.properties.uri import URI

if TYPE_CHECKING:
    from mytunes.core.api.user import HasUserEndpoints, UserEndpoints


class User(HasName, HasImages):
    type: ClassVar[str] = "user"

    name: StrippedString = Field(
        description="The display name of the user",
    )


class RemoteUser[UT: URI](User, RemoteResource[UT]):
    email: EmailStr | None = Field(
        description="The email associated with the user",
        default=None,
    )

    # @validate_call  # can't validate as can't import these types at runtime due to cyclical imports
    async def reload(self, api: HasUserEndpoints[UserEndpoints]) -> Self:
        model = await api.users.get_me()
        self.__dict__.update(model.__dict__)
        return model
