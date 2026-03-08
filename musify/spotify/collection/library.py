from typing import Any, final, ClassVar

from musify.remote.collection.library import RemoteMutableLibrary
from musify.spotify import SpotifyModel
from musify.spotify.collection.playlist import SpotifyMutablePlaylist
from musify.spotify.item.track import SpotifyTrack
from musify.spotify.properties.followers import HasFollowers


@final
class SpotifyLibrary(
    SpotifyModel,
    RemoteMutableLibrary[str, SpotifyTrack, str, SpotifyMutablePlaylist],
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
