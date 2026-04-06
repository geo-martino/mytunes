from typing import ClassVar, final

from yarl import URL

from musify._models.api.user import UserEndpoints
from musify.spotify import API_URL
from musify.spotify._api._base import SpotifyEndpoints
from musify.spotify.user import SpotifyUser
from .._properties.uri import SpotifyUserURI


@final
class SpotifyUserEndpoints(
    SpotifyEndpoints[SpotifyUserURI, SpotifyUser],
    UserEndpoints[SpotifyUserURI, SpotifyUser],
):
    __final__ = True

    _me_url: ClassVar[URL] = API_URL.joinpath("me")
