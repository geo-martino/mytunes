from musify.remote.api import RemoteAPI
from musify.remote.api.album import HasAlbumEndpoints
from musify.remote.api.artist import HasArtistEndpoints
from musify.remote.api.playlist import HasPlaylistEndpoints
from musify.remote.api.search import HasSearchEndpoints
from musify.remote.api.track import HasTrackEndpoints
from musify.remote.api.user import HasUserEndpoints
from musify.spotify import SpotifyModel
from musify.spotify.api._album import SpotifyAlbumEndpoints
from musify.spotify.api._artist import SpotifyArtistEndpoints
from musify.spotify.api._auth import SpotifyAuthoriser
from musify.spotify.api._playlist import SpotifyPlaylistEndpoints
from musify.spotify.api._search import SpotifySearchEndpoints
from musify.spotify.api._track import SpotifyTrackEndpoints
from musify.spotify.api._user import SpotifyUserEndpoints


class SpotifyAPI(
    RemoteAPI[SpotifyAuthoriser],
    SpotifyModel,
    HasSearchEndpoints[SpotifySearchEndpoints],
    HasUserEndpoints[SpotifyUserEndpoints],
    HasTrackEndpoints[SpotifyTrackEndpoints],
    HasPlaylistEndpoints[SpotifyPlaylistEndpoints],
    HasAlbumEndpoints[SpotifyAlbumEndpoints],
    HasArtistEndpoints[SpotifyArtistEndpoints],
):
    pass
