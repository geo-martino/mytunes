from musify.local.collection._base import LocalCollection
from musify.local.collection.playlist import LocalPlaylist
from musify.local.item.track import LocalTrack
from musify.models.collection.library import MutableLibrary


class LocalLibrary(
    LocalCollection, MutableLibrary[str, LocalTrack, str, LocalPlaylist]
):
    async def load(self):
        pass

    async def load_tracks(self) -> None:
        pass

    def log_tracks(self) -> None:
        pass

    async def load_playlists(self) -> None:
        pass

    def log_playlists(self) -> None:
        pass

