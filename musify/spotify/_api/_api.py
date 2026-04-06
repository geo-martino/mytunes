from aiorequestful.cache.backend import ResponseCache
from aiorequestful.cache.backend.base import ResponseRepository
from yarl import URL

from musify.models.api import RemoteAPI
from musify.models.api._base import HasCache
from musify.models.api.items import HasAlbumEndpoints, HasArtistEndpoints, HasTrackEndpoints
from musify.models.api.playlist import HasPlaylistEndpoints
from musify.models.api.search import HasSearchEndpoints
from musify.models.api.user import HasUserEndpoints
from musify.spotify import SpotifyModel
from musify.spotify._api.album import SpotifyAlbumEndpoints
from musify.spotify._api.artist import SpotifyArtistEndpoints
from musify.spotify._api.auth import SpotifyAuthoriser
from musify.spotify._api.cache import SpotifyRepositorySettings, SpotifyIndexCursorRepositorySettings
from musify.spotify._api.playlist import SpotifyPlaylistEndpoints
from musify.spotify._api.search import SpotifySearchEndpoints
from musify.spotify._api.track import SpotifyTrackEndpoints
from musify.spotify._api.user import SpotifyUserEndpoints


class SpotifyAPI(
    RemoteAPI[SpotifyAuthoriser],
    SpotifyModel,
    HasCache,
    HasSearchEndpoints[SpotifySearchEndpoints],
    HasUserEndpoints[SpotifyUserEndpoints],
    HasTrackEndpoints[SpotifyTrackEndpoints],
    HasPlaylistEndpoints[SpotifyPlaylistEndpoints],
    HasAlbumEndpoints[SpotifyAlbumEndpoints],
    HasArtistEndpoints[SpotifyArtistEndpoints],
):
    # TODO: amend this on aiorequestful v2
    # noinspection PyAsyncCall
    async def _setup_cache(self, cache: ResponseCache) -> None:
        cache.repository_getter = self._get_cache_repository

        cache.create_repository(SpotifyRepositorySettings(name="tracks"))
        cache.create_repository(SpotifyRepositorySettings(name="audio_features"))
        cache.create_repository(SpotifyRepositorySettings(name="audio_analysis"))

        cache.create_repository(SpotifyRepositorySettings(name="albums"))
        cache.create_repository(SpotifyIndexCursorRepositorySettings(name="album_tracks", default_limit=20))

        cache.create_repository(SpotifyRepositorySettings(name="artists"))
        cache.create_repository(SpotifyIndexCursorRepositorySettings(name="artist_albums", default_limit=5))

        cache.create_repository(SpotifyRepositorySettings(name="shows"))
        cache.create_repository(SpotifyRepositorySettings(name="episodes"))
        cache.create_repository(SpotifyIndexCursorRepositorySettings(name="show_episodes", default_limit=20))

        cache.create_repository(SpotifyRepositorySettings(name="audiobooks"))
        cache.create_repository(SpotifyRepositorySettings(name="chapters"))
        cache.create_repository(SpotifyIndexCursorRepositorySettings(name="audiobook_chapters", default_limit=20))

        await cache

    # TODO: amend this on aiorequestful v2
    @staticmethod
    def _get_cache_repository(cache: ResponseCache, url: URL) -> ResponseRepository | None:
        path = URL(url).path
        path_split = [part.replace("-", "_") for part in path.split("/")[2:]]

        if len(path_split) < 3:
            name = path_split[0]
        else:
            name = f"{path_split[0].rstrip("s")}_{path_split[2].rstrip("s") + "s"}"

        return cache.get(name)
