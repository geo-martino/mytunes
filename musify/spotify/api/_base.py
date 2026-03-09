from typing import ClassVar

from aiorequestful.auth import Authoriser

from musify.remote.api import RemoteEndpoints, RemoteGetSingleEndpoints, RemoteGetManyEndpoints, \
    RemoteGetSavedEndpoints, RemoteMutableSavedEndpoints, RemoteCollectionEndpoints, RemoteMutableCollectionEndpoints
from musify.spotify import SpotifyModel, SpotifyResource
from musify.spotify.properties.uri import _SpotifyURIBase


class SpotifyEndpoints[UT: _SpotifyURIBase, RT: SpotifyResource](
    RemoteEndpoints[UT, RT], SpotifyModel
):
    pass
