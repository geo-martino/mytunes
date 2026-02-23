from copy import copy, deepcopy
from pathlib import Path
from random import choice, sample
from typing import Any

import pytest
from aiorequestful.cache.backend.base import ResponseCache, ResponseRepository
from aiorequestful.cache.exception import CacheError
from aiorequestful.cache.session import CachedSession
from yarl import URL

from musify._types import Resource
from musify.libraries.remote.core.exception import APIError
from musify.libraries.remote.spotify.api import SpotifyAPI
from tests.libraries.remote.spotify.api.mock import SpotifyMock
from tests.libraries.remote.spotify.api.testers import SpotifyAPIFixtures
from tests.libraries.remote.spotify.utils import random_id
from tests.utils import random_str, idfn


class TestSpotifyAPI(SpotifyAPIFixtures):

    items_key = SpotifyAPI.items_key

    # noinspection PyTestUnpassedFixture
    def test_init(self, cache: ResponseCache):
        client_id = "CLIENT_ID"
        client_secret = "CLIENT_SECRET"
        scopes = ["scope 1", "scope 2"]
        token_file_path = "i am a path to a file.json"

        api = SpotifyAPI(
            client_id=client_id,
            client_secret=client_secret,
            scope=scopes,
            cache=cache,
            token_file_path=token_file_path,
        )

        assert api.handler.authoriser.service_name == api.wrangler.source
        assert api.handler.authoriser.user_request.params["client_id"] == client_id
        assert api.handler.authoriser.user_request.params["scope"] == " ".join(scopes)
        assert api.handler.authoriser.response.file_path == Path(token_file_path)

    # noinspection PyTestUnpassedFixture
    async def test_context_management(self, cache: ResponseCache, api_mock: SpotifyMock):
        api = SpotifyAPI(cache=cache)
        api.handler.authoriser.response.replace({
            "access_token": "fake access token", "token_type": "Bearer", "scope": "test-read"
        })

        with pytest.raises(APIError):
            assert api.user_id

        async with api as a:
            assert a.user_id == api_mock.user_id
            assert len(a.user_playlist_data) == len(api_mock.user_playlists)

            assert isinstance(a.handler.session, CachedSession)
            assert a.handler.session.cache.cache_name == cache.cache_name

            expected_names = [
                "tracks",
                "audio_features",
                "audio_analysis",
                "albums",
                "artists",
                "episodes",
                "chapters",
                "album_tracks",
                "artist_albums",
                "show_episodes",
                "audiobook_chapters"
            ]

            assert all(name in cache for name in expected_names)

            repository = choice(list(a.handler.session.cache.values()))
            await repository.count()  # just check this doesn't fail

    # noinspection PyTestUnpassedFixture
    async def test_cache_repository_getter(self, cache: ResponseCache, api_mock: SpotifyMock):
        api = SpotifyAPI(cache=cache)
        api.handler.authoriser.response.replace({
            "access_token": "fake access token", "token_type": "Bearer", "scope": "test-read"
        })
        async with api as a:
            name_url_map = {
                "tracks": f"{a.wrangler.url_api}/tracks/{random_id()}",
                "artists": f"{a.wrangler.url_api}/artists?ids={",".join(random_id() for _ in range(10))}",
                "albums": f"{a.wrangler.url_api}/albums?ids={",".join(random_id() for _ in range(50))}",
                "audio_features":
                    f"{a.wrangler.url_api}/audio-features?ids={",".join(random_id() for _ in range(10))}",
                "audio_analysis": f"{a.wrangler.url_api}/audio-analysis/{random_id()}",
            }
            names_paginated = ["artist_albums", "album_tracks"]
            for name in names_paginated:
                parent, child = name.split("_")
                parent = parent.rstrip("s") + "s"
                child = child.rstrip("s") + "s"

                url = f"{a.wrangler.url_api}/{parent}/{random_id()}/{child}"
                name_url_map[name] = url

            for name, url in name_url_map.items():
                repository = cache.get_repository_from_url(url)
                assert repository.settings.name == name

            # un-cached URLs
            assert cache.get_repository_from_url(f"{a.wrangler.url_api}/me/albums") is None
            assert cache.get_repository_from_url(f"{a.wrangler.url_api}/search") is None
            assert cache.get_repository_from_url(f"{a.wrangler.url_api}/playlists/{random_id()}/followers") is None
            assert cache.get_repository_from_url(f"{a.wrangler.url_api}/users/{random_str(10, 30)}/playlists") is None

    ###########################################################################
    ## Utilities: Formatters
    ###########################################################################
    def test_format_key(self, api: SpotifyAPI):
        object_type = Resource.PLAYLIST
        assert api._format_key(object_type) == "playlists"
        assert api._format_key("playlists") == "playlists"
        assert api._format_key("audio_feature") == "audio_features"
        assert api._format_key(None) is None

    def test_format_next_url(self, api: SpotifyAPI):
        url = f"{api.wrangler.url_api}/tracks"
        assert api.format_next_url(url, 15, 29) == f"{url}?offset=15&limit=29"

        params = {"key1": "value1", "key2": "value2"}
        url = str(URL(url).with_query(params))
        assert api.format_next_url(url, 15, 29) == f"{url}&offset=15&limit=29"

    ###########################################################################
    ## Utilities: Enrich responses
    ###########################################################################
    def test_enrich_with_identifiers(self, api: SpotifyAPI):
        response = {}
        id_ = random_id()
        href = str(URL(f"{api.wrangler.url_api}/tracks").with_path(f"tracks/{random_id()}"))

        api._enrich_with_identifiers(response=response, id_=id_, href=href)
        assert response[self.id_key] == id_
        assert response[self.url_key] == href

        response[self.id_key] = "some random id"
        response[self.url_key] = "some random url"

        api._enrich_with_identifiers(response=response, id_=id_, href=href)
        assert response[self.id_key] != id_
        assert response[self.url_key] != href

    @staticmethod
    def assert_items_not_enriched_with_parent_response(items: list[dict[str, Any]], parent_key: str):
        """Check no enrich happened"""
        for item in items:
            assert parent_key not in item

    @pytest.mark.parametrize("object_type", [
        Resource.ALBUM, Resource.SHOW, Resource.AUDIOBOOK,
    ], ids=idfn)
    def test_enrich_with_parent_response(
            self,
            object_type: Resource,
            key: str,
            response: dict[str, Any],
            api: SpotifyAPI,
            api_mock: SpotifyMock
    ):
        item_type = api.collection_item_map[object_type]
        parent_key = object_type.name.lower()
        parent_response = response
        assert key in parent_response

        items = deepcopy(sample(api_mock.item_type_map[item_type], k=10))
        for item in items:
            item.pop(parent_key, None)
        test = api_mock.format_items_block(url=parent_response[self.url_key], items=items)

        # skips on parent keys which are strings or invalid
        api._enrich_with_parent_response(
            response=test, key=key, parent_key=None, parent_response=parent_response
        )
        self.assert_items_not_enriched_with_parent_response(items, parent_key)
        api._enrich_with_parent_response(
            response=test, key=key, parent_key=parent_key, parent_response=parent_response
        )
        self.assert_items_not_enriched_with_parent_response(items, parent_key)

        # skips on playlist responses
        api._enrich_with_parent_response(
            response=test, key=key, parent_key=Resource.PLAYLIST, parent_response=parent_response
        )
        self.assert_items_not_enriched_with_parent_response(items, parent_key)

        # skips because parent response is not correct format, expects it to not be items block
        api._enrich_with_parent_response(
            response=items[0],
            key=key,
            parent_key=object_type,
            parent_response=api_mock.format_items_block(url=parent_response[self.url_key], items=[parent_response])
        )
        self.assert_items_not_enriched_with_parent_response(items, parent_key)

        # skips because input response is not correct format, expects items block
        api._enrich_with_parent_response(
            response=items[0], key=key, parent_key=object_type, parent_response=parent_response
        )
        self.assert_items_not_enriched_with_parent_response(items, parent_key)

        # skips on empty parent response after dropping key
        api._enrich_with_parent_response(
            response=items[0], key=key, parent_key=object_type, parent_response={key: "some random value"}
        )
        self.assert_items_not_enriched_with_parent_response(items, parent_key)

        # with valid values
        api._enrich_with_parent_response(
            response=test, key=key, parent_key=object_type, parent_response=parent_response
        )

        for item in items:
            assert item[parent_key] == {k: v for k, v in parent_response.items() if k != key}

        # does not enrich when parent key already present
        parent_response = copy(parent_response)
        parent_response["new key"] = "new value"

        api._enrich_with_parent_response(
            response=test, key=key, parent_key=object_type, parent_response=parent_response
        )
        for item in items:
            assert "new key" not in item[parent_key]
            assert item[parent_key] != {k: v for k, v in parent_response.items() if k != key}

    ###########################################################################
    ## Utilities: Caching
    ###########################################################################
    @pytest.mark.parametrize("object_type", [
        Resource.PLAYLIST, Resource.USER,
    ], ids=idfn)
    async def test_get_responses_from_cache_skips(
            self,
            object_type: Resource,
            responses: dict[str, dict[str, Any]],
            api: SpotifyAPI,
            api_cache: SpotifyAPI,
            api_mock: SpotifyMock
    ):
        url = f"{api.url}/{object_type.name.lower()}s"
        id_list = list(responses.keys())

        # skip when no cache present
        assert not isinstance(api.handler.session, CachedSession) is None
        assert await api._get_responses_from_cache(method="GET", url=url, id_list=id_list) == ([], [], id_list)

        # skip when no repository found
        assert await api_cache._get_responses_from_cache(method="GET", url=url, id_list=id_list) == ([], [], id_list)

    @pytest.mark.parametrize("object_type", [
        Resource.TRACK,
        Resource.ALBUM,
        Resource.ARTIST,
        Resource.SHOW,
        Resource.EPISODE,
        Resource.AUDIOBOOK,
        Resource.CHAPTER,
    ], ids=idfn)
    async def test_get_responses_from_cache(
            self,
            object_type: Resource,
            responses: dict[str, dict[str, Any]],
            repository: ResponseRepository,
            api_cache: SpotifyAPI,
            api_mock: SpotifyMock
    ):
        url = f"{api_cache.url}/{object_type.name.lower()}s"
        id_list = list(responses)
        limit = len(responses) - 3
        method = "GET"

        responses_remapped = {(method, id_): response for id_, response in list(responses.items())[:limit]}
        await repository.save_responses(responses_remapped)
        assert all([await repository.contains((method, id_)) for id_ in id_list[:limit]])

        results, found, not_found = await api_cache._get_responses_from_cache(method=method, url=url, id_list=id_list)
        assert len(results) == len(found) == limit
        assert len(not_found) == len(responses) - limit
        assert results == list(responses.values())[:limit]

        api_mock.assert_not_called()

    @pytest.mark.parametrize("object_type", [
        Resource.TRACK,
        Resource.ALBUM,
        Resource.ARTIST,
        Resource.SHOW,
        Resource.EPISODE,
        Resource.AUDIOBOOK,
    ], ids=idfn)
    async def test_cache_responses_skips_and_fails(
            self,
            object_type: Resource,
            responses: dict[str, dict[str, Any]],
            repository: ResponseRepository,
            api: SpotifyAPI,
            api_cache: SpotifyAPI,
            api_mock: SpotifyMock
    ):
        # skips when no cache present i.e. handler does not contain a CachedSession
        responses = list(responses.values())
        await api._cache_responses(method="GET", responses=responses)
        assert await repository.count() == 0

        # user items usually don't contain a URL key in their base mapping, should skip
        user_responses = deepcopy(sample(api_mock.item_type_map_user[object_type], k=10))
        for response in user_responses:
            response.pop(self.url_key, None)
        await api_cache._cache_responses(method="GET", responses=user_responses)
        assert await repository.count() == 0

        # too many different types of responses given, should raise an error
        other_object_type = choice([enum for enum in Resource.all() if enum != object_type])
        responses += deepcopy(sample(api_mock.item_type_map[other_object_type], k=10))
        with pytest.raises(CacheError):
            await api_cache._cache_responses(method="GET", responses=responses)

    @pytest.mark.parametrize("object_type", [
        Resource.PLAYLIST, Resource.USER,
    ], ids=idfn)
    async def test_cache_responses_skips_on_no_repository(
            self,
            object_type: Resource,
            responses: dict[str, dict[str, Any]],
            repository: ResponseRepository,
            api_cache: SpotifyAPI,
    ):
        responses = list(responses.values())
        assert repository is None
        await api_cache._cache_responses(method="GET", responses=responses)

    @pytest.mark.parametrize("object_type", [
        Resource.TRACK,
        Resource.ALBUM,
        Resource.ARTIST,
        Resource.SHOW,
        Resource.EPISODE,
        Resource.AUDIOBOOK,
        Resource.CHAPTER,
    ], ids=idfn)
    async def test_cache_responses(
            self,
            object_type: Resource,
            responses: dict[str, dict[str, Any]],
            repository: ResponseRepository,
            api_cache: SpotifyAPI,
    ):
        responses = list(responses.values())
        await api_cache._cache_responses(method="GET", responses=responses)
        assert await repository.count() == len(responses)

    @pytest.fixture(params=["audio_features", "audio_analysis"])
    def special_type(self, request) -> str:
        """Special object type keys to test"""
        return request.param

    @pytest.fixture
    def special_responses(self, special_type: str, api_mock: SpotifyMock) -> dict[str, dict[str, Any]]:
        """Responses for the special object type keys to test"""
        return dict(deepcopy(sample(list(api_mock.audio_features.items()), k=10)))

    @pytest.fixture
    def special_repository(self, special_type: str, cache: ResponseCache, api_cache: SpotifyAPI) -> ResponseRepository:
        """The repository in the ``cache`` relating to the special object type under test"""
        return cache[special_type]

    async def test_cache_responses_on_special_endpoints(
            self,
            special_type: str,
            special_responses: dict[str, dict[str, Any]],
            special_repository: ResponseRepository,
            api_cache: SpotifyAPI,
    ):
        for id_, response in special_responses.items():
            path = f"{special_type.replace("_", "-")}/{id_}"
            url = f"{api_cache.wrangler.url_api}/{path}"
            response[self.url_key] = url

        await api_cache._cache_responses(method="GET", responses=special_responses.values())
        assert await special_repository.count() == len(special_responses)
