from typing import final

from mytunes.spotify import SpotifyModel
from mytunes.spotify._collection.playlist import SpotifyPlaylist
from mytunes.spotify.user import SpotifyUser
from .._api import SpotifyAPI
from .._item.album import SpotifyAlbum
from .._item.artist import SpotifyArtist
from .._item.genre import SpotifyGenre
from .._item.track import SpotifyTrack
from .._properties.stats import HasFollowers
from ..._models.collection.library import RemoteMutableLibrary


@final
class SpotifyLibrary(
    SpotifyModel,
    RemoteMutableLibrary[
        SpotifyAPI,
        SpotifyTrack,
        SpotifyPlaylist,
        SpotifyArtist,
        SpotifyAlbum,
        SpotifyGenre,
        SpotifyUser
    ],
    HasFollowers,
):
    __final__ = True
