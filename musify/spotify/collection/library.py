from typing import final

from musify.models.collection.library import RemoteMutableLibrary
from musify.spotify import SpotifyModel
from musify.spotify.collection.playlist import SpotifyMutablePlaylist
from musify.spotify.item.album import SpotifyAlbum
from musify.spotify.item.artist import SpotifyArtist
from musify.spotify.item.genre import SpotifyGenre
from musify.spotify.item.track import SpotifyTrack
from musify.spotify.properties.followers import HasFollowers
from musify.spotify.user import SpotifyUser


@final
class SpotifyLibrary(
    SpotifyModel,
    RemoteMutableLibrary[
        str, SpotifyTrack, str, SpotifyMutablePlaylist, SpotifyArtist, SpotifyAlbum, SpotifyGenre, SpotifyUser
    ],
    HasFollowers,
):
    __final__ = True
