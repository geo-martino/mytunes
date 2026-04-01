from typing import ClassVar

from musify.models.api import Endpoints
from musify.spotify import SpotifyModel, SpotifyResource
from musify.spotify.properties.uri import _SpotifyURIBase


class SpotifyEndpoints[UT: _SpotifyURIBase, RT: SpotifyResource](
    Endpoints[UT, RT], SpotifyModel
):
    # TODO: drop this on aiorequestful v2
    _id_path: ClassVar[str] = "id"
    _url_path: ClassVar[str] = "href"
