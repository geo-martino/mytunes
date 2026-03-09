from typing import ClassVar, final

from aiorequestful.auth import Authoriser
from yarl import URL

from musify.remote.api.user import UserEndpoints
from musify.spotify import API_URL
from musify.spotify.user import SpotifyUser
from musify.spotify.properties.uri import SpotifyUserURI
from musify.spotify.api._base import SpotifyEndpoints


@final
class SpotifyUserEndpoints(
    SpotifyEndpoints[SpotifyUserURI, SpotifyUser],
    UserEndpoints[SpotifyUserURI, SpotifyUser],
):
    __final__ = True

    _me_url: ClassVar[URL] = API_URL.joinpath("me")
