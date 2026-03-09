from typing import ClassVar

from pydantic import Field, PrivateAttr
from yarl import URL

from musify.models.properties.uri import URI
from musify.remote.api._endpoints import RemoteEndpoints, HasEndpoints
from musify.remote.user import RemoteUser


class UserEndpoints[UT: URI, RT: RemoteUser](RemoteEndpoints[UT, RT]):
    type: ClassVar[str] = "user"

    _me_url: ClassVar[URL] = PrivateAttr(
        # description="The API endpoint to get the current user.",
    )

    async def get_me(self) -> RT:
        """Get the current user."""
        response = await self._handler.get(self._me_url)
        return self.__class__.create_model(response)


class UserGetSingleEndpoints[UT: URI, RT: RemoteUser](
    UserEndpoints[UT, RT], RemoteEndpoints[UT, RT]
):
    pass


class HasUserEndpoints[ET: UserEndpoints](HasEndpoints):
    users: ET = Field(
        description="Access user endpoints for the API."
    )
