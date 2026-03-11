from musify.models.api import RemoteAPI
from musify.models.api.album import HasAlbumEndpoints
from musify.models.api.artist import HasArtistEndpoints
from musify.models.api.playlist import HasPlaylistEndpoints
from musify.models.api.search import HasSearchEndpoints
from musify.models.api.track import HasTrackEndpoints
from musify.models.api.user import HasUserEndpoints
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
