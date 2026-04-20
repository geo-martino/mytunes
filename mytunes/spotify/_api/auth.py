from collections.abc import Sequence
from http import HTTPMethod
from pathlib import Path
from typing import ClassVar

from aiohttp import ClientResponse, ClientResponseError
from aiorequestful.auth.oauth2 import AuthorisationCodeFlow
from aiorequestful.auth.utils import AuthRequest
from pydantic import SecretStr, Field, field_validator, PrivateAttr
from yarl import URL

from mytunes.spotify import SpotifyModel, API_URL
from mytunes.spotify.exception import SpotifyAuthenticationError
from ...core.api import RemoteAuthoriser


class SpotifyAuthoriser(RemoteAuthoriser[AuthorisationCodeFlow], SpotifyModel):
    _url_auth: ClassVar[URL] = PrivateAttr(
        default=URL.build(scheme="https", host="accounts.spotify.com")
    )

    client_id: SecretStr = Field(
        description="The client ID of the Spotify application.",
    )
    client_secret: SecretStr = Field(
        description="The client secret of the Spotify application.",
    )
    scope: Sequence[str] = Field(
        description="A list of scopes that the client can use to access the Spotify application.",
        default_factory=list,
    )
    token_file_path: Path | None = Field(
        description="The path to a file containing a stored access token response for the Spotify application.",
        default=None,
    )

    @field_validator("scope", mode="before")
    @classmethod
    def _split_scope[T](cls, scope: T | str) -> T | tuple[str, ...]:
        if not isinstance(scope, str):
            return scope
        return tuple(scope.split())

    def create_authoriser(self) -> AuthorisationCodeFlow:
        """Create an authoriser for the Spotify API using the provided credentials and scopes."""
        authoriser = AuthorisationCodeFlow.create_with_encoded_credentials(
            service_name=self.source,
            user_request_url=self._url_auth.with_path("authorize"),
            token_request_url=self._url_auth.with_path("api/token"),
            refresh_request_url=self._url_auth.with_path("api/token"),
            client_id=self.client_id.get_secret_value(),
            client_secret=self.client_secret.get_secret_value(),
            scope=self.scope,
        )

        token_request = authoriser.token_request
        if not hasattr(token_request, "headers"):
            token_request.headers = {}
        token_request.headers["content-type"] = "application/x-www-form-urlencoded"

        # WORKAROUND: maybe need to fix the redirect URI in the base package to use 127.0.0.1 instead of localhost?
        authoriser.redirect_uri = authoriser.redirect_uri.with_host("127.0.0.1")

        if not hasattr(authoriser.refresh_request, "headers"):
            authoriser.refresh_request.headers = {}
        authoriser.refresh_request.headers["content-type"] = "application/x-www-form-urlencoded"

        if self.token_file_path:
            authoriser.response.file_path = self.token_file_path
        authoriser.response.additional_headers = {
            "Accept": "application/json", "Content-Type": "application/json"
        }

        authoriser.tester.request = AuthRequest(
            method=HTTPMethod.GET, url=API_URL.joinpath("me")
        )
        authoriser.tester.response_test = self._response_test
        authoriser.tester.max_expiry = 600

        return authoriser

    @staticmethod
    async def _response_test(response: ClientResponse) -> bool:
        try:
            r = await response.json()
            return "href" in r and "display_name" in r
        except ClientResponseError:
            if "premium subscription" in await response.text():
                raise SpotifyAuthenticationError(
                    "The access token is valid but the Spotify API cannot be accessed with a free account. "
                    "A premium subscription is required."
                )
            raise
