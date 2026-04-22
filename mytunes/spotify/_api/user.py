from typing import ClassVar, final

from yarl import URL

from mytunes.spotify import API_URL
from mytunes.spotify._api._base import SpotifyEndpoints
from mytunes.spotify.user import SpotifyUser
from .._properties.uri import SpotifyUserURI
from ...core.api.user import UserEndpoints


@final
class SpotifyUserEndpoints(
    SpotifyEndpoints[SpotifyUserURI, SpotifyUser],
    UserEndpoints[SpotifyUserURI, SpotifyUser],
):
    __final__ = True

    _me_url: ClassVar[URL] = API_URL.joinpath("me")
