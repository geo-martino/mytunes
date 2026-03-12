from typing import ClassVar, Type

from pydantic import Field, PrivateAttr
from yarl import URL

from musify.models.properties.uri import URI
from musify.models.api import Endpoints, HasEndpoints
from musify.models.user import RemoteUser


class UserEndpoints[UT: URI, RT: RemoteUser](Endpoints[UT, RT]):
    type: ClassVar[Type] = RemoteUser

    _me_url: ClassVar[URL] = PrivateAttr(
        # description="The API endpoint to get the current user.",
    )

    async def get_me(self) -> RT:
        """Get the current user."""
        response = await self._handler.get(self._me_url)
        return self.__class__.create_model(response)


class HasUserEndpoints[ET: UserEndpoints](HasEndpoints):
    users: ET = Field(
        description="Access user endpoints for the API."
    )
