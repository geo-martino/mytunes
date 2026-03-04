from typing import Any, final

from musify.remote.collection.library import RemoteLibrary
from musify.spotify.collection._base import SpotifyCollection
from musify.spotify.collection.playlist import SpotifyMutablePlaylist
from musify.spotify.item.track import SpotifyTrack
from musify.spotify.properties.followers import HasFollowers


@final
class SpotifyLibrary(
    RemoteLibrary[str, SpotifyTrack, str, SpotifyMutablePlaylist],
    SpotifyCollection,
    HasFollowers,
):
    __final__ = True

    async def load(self):
        pass

    async def load_tracks(self) -> None:
        pass

    def log_tracks(self) -> Any:
        pass

    async def load_playlists(self) -> None:
        pass

    def log_playlists(self) -> Any:
        pass
