from typing import Any, final

from pydantic import Field

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

    total: int | None = Field(
        description="The total number of tracks and playlists saved by this user.",
        default=None,
    )

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
