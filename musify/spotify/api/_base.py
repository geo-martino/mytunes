from musify.models.api import Endpoints
from musify.spotify import SpotifyModel, SpotifyResource
from musify.spotify.properties.uri import _SpotifyURIBase


class SpotifyEndpoints[UT: _SpotifyURIBase, RT: SpotifyResource](
    Endpoints[UT, RT], SpotifyModel
):
    pass
