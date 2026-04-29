from typing import ClassVar, Self

from pydantic import Field, PrivateAttr
from yarl import URL

from mytunes.core.api import Endpoints, HasEndpoints
from mytunes.core.properties.uri import URI
from .._item.user import RemoteUser


class UserEndpoints[UT: URI, RT: RemoteUser](Endpoints[UT, RT]):
    _me_url: ClassVar[URL] = PrivateAttr(
        # description="The API endpoint to get the current user.",
    )

    async def __aenter__(self) -> Self:
        await super().__aenter__()
        self.user = await self.get_me()
        return self

    async def get_me(self) -> RT:
        """Get the current user."""
        response = await self._handler.get(self._me_url)
        return type(self).create_model(response, context=self._model_context)


class HasUserEndpoints[ET: UserEndpoints](HasEndpoints[ET]):
    users: ET = Field(
        description="Access user endpoints for the API."
    )

    @property
    def user(self) -> RemoteUser | None:
        """The currently authenticated user, if available."""
        return self.users.user

    @user.setter
    def user(self, value: RemoteUser | None) -> None:
        self.users.user = value

        # set for all other nested endpoints
        for endpoints in self._nested_endpoints:
            endpoints.user = value

    async def __aenter__(self) -> Self:
        await super().__aenter__()
        self.user = self.users.user
        return self
