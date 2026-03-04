from musify.remote import RemoteModel, RemoteResource
from musify.spotify.properties.uri import _SpotifyURIBase


class SpotifyModel(RemoteModel):
    pass


class SpotifyResource[UT: _SpotifyURIBase](RemoteResource[UT], SpotifyModel):
    pass
