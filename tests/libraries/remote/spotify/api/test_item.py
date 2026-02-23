from collections.abc import Collection
from copy import deepcopy
from itertools import batched
from random import sample, randrange, choice
from typing import Any
from urllib.parse import unquote

import pytest
from yarl import URL

from musify._types import Resource
from musify.libraries.remote.core import RemoteResponse
from musify.libraries.remote.core.exception import APIError, RemoteObjectTypeError
from musify.libraries.remote.core.object import RemoteCollection
from musify.libraries.remote.core.types import RemoteIDType
from musify.libraries.remote.spotify.api import SpotifyAPI
from musify.libraries.remote.spotify.factory import SpotifyObjectFactory
from musify.libraries.remote.spotify.object import SpotifyPlaylist, SpotifyAlbum, SpotifyTrack
from tests.libraries.remote.core.api import RemoteAPIItemTester
from tests.libraries.remote.core.utils import ALL_ITEM_TYPES
from tests.libraries.remote.spotify.api.mock import SpotifyMock
from tests.libraries.remote.spotify.api.testers import SpotifyAPIFixtures
from tests.libraries.remote.spotify.api.utils import get_limit, assert_calls
from tests.libraries.remote.spotify.utils import random_ids, random_id, random_id_type, random_id_types
from tests.utils import idfn, random_str


class TestSpotifyAPIItems(RemoteAPIItemTester, SpotifyAPIFixtures):
    """Tester for item-type endpoints of :py:class:`SpotifyAPI`"""

    items_key = SpotifyAPI.items_key

    ###########################################################################
    ## Assertions
    ###########################################################################
    @staticmethod
    def assert_item_types(results: list[dict[str, Any]], key: str, object_type: Resource | None = None):
        """
        Assert all items are of the correct type by checking the result at key 'type' has value ``key``.
        Provide an ``object_type`` to apply object_type specific logic.
        """
        key = key.rstrip("s")
        for result in results:
            if object_type == Resource.PLAYLIST:
                # playlist responses next items deeper under 'track' key
                assert result[key]["type"] == key
            else:
                assert result["type"] == key

    def assert_get_items_results(
            self,
            results: list[dict[str, Any]],
            expected: dict[str, dict[str, Any]],
            test: dict[str, dict[str, Any]] | None = None,
            object_type: Resource | None = None,
            key: str | None = None,
    ):
        """
        Various assertions for get_items method results.

        - Assert the length of ``results`` and ``expected`` match
        - If ``key`` is not given, assume the given results relate to a collection and run assertions on its sub-items.
          If not given, just simply check each result is the same as its expected value.
        - If ``test`` is given, further assert the originally input ``test`` API response values
          were updated by the get_items operation.
        """
        assert len(results) == len(expected)

        for result in results:
            expect = expected[result[self.id_key]]
            if not key:  # get_items ran with no extension
                # no sub-items so responses are relatively small
                # we can therefore assert result == expected as it is a relatively quick comparison
                assert result == expect
                if test:
                    assert test[result[self.id_key]] == result
                continue

            # get_items ran and extended the initial results
            # just check length of sub-items match and objet_types are correct
            # fully checking result == expected would take too long as responses are normally very large

            assert len(result[key][self.items_key]) == expect[key]["total"]
            self.assert_item_types(results=result[key][self.items_key], object_type=object_type, key=key)
            self.assert_similar(expect, result, key)

            if test:
                assert len(test[result[self.id_key]][key][self.items_key]) == expect[key]["total"]
                self.assert_similar(expect, test[result[self.id_key]], key)

    async def assert_get_items_calls(
            self,
            responses: Collection[dict[str, Any]],
            object_type: Resource,
            api: SpotifyAPI,
            api_mock: SpotifyMock,
            key: str | None = None,
            limit: int | None = None,
    ):
        """Assert appropriate number of requests made for get_items method calls"""
        url = f"{api.url}/{object_type.name.lower()}s"
        requests = await api_mock.get_requests(url=url)
        for response in responses:
            if limit is None or object_type in {Resource.USER, Resource.PLAYLIST}:
                requests += await api_mock.get_requests(url=f"{url}/{response[self.id_key]}")
            if key:
                requests += await api_mock.get_requests(url=f"{url}/{response[self.id_key]}/{key}")
        assert_calls(expected=responses, requests=requests, key=key, limit=limit, api_mock=api_mock)

    @staticmethod
    def assert_response_extended[T: RemoteResponse](actual: T, expected: T):
        """
        Check that a :py:class:`RemoteResponse` has been refreshed
        by asserting that the items in its collection have been extended.
        Ignores any RemoteResponse that is not also a :py:class:`MusifyCollection`
        """
        if not isinstance(actual, RemoteCollection):
            return

        if isinstance(actual, SpotifyPlaylist):
            assert len(actual.tracks) == actual.track_total > len(expected.tracks)
        elif isinstance(actual, SpotifyAlbum):
            assert len(actual.tracks) == actual.track_total > len(expected.tracks)

    def assert_response_enriched_with_parent(self, object_type: Resource, key: str, response: dict[str, Any]):
        """Check that the child items in the given ``response`` have been enriched with its parent response"""
        if object_type == Resource.PLAYLIST:
            return

        parent_key = object_type.name.lower()
        parent_response = {k: v for k, v in response.items() if k != key}

        assert self.items_key not in parent_response
        assert "next" not in parent_response
        assert "previous" not in parent_response
        assert "total" not in parent_response

        for item in response[key][self.items_key]:
            assert parent_key in item
            assert item[parent_key] == parent_response

    ###########################################################################
    ## Basic functionality
    ###########################################################################
    def test_get_unit(self, api: SpotifyAPI):
        assert api._get_unit() == api.items_key
        assert api._get_unit(key="track") == "tracks"
        assert api._get_unit(kind="Audio Features") == "audio features"
        assert api._get_unit(kind="Audio Features", key="tracks") == "audio features"
        assert api._get_unit(key="audio-features") == "audio features"

    async def test_get_items_batches_limited(self, api: SpotifyAPI, api_mock: SpotifyMock):
        key = Resource.TRACK.name.lower() + "s"
        url = f"{api.url}/{key}"
        id_list = [track[self.id_key] for track in api_mock.tracks]
        valid_limit = randrange(api_mock.limit_lower + 1, api_mock.limit_upper - 1)

        id_list_reduced = sample(id_list, k=api_mock.limit_lower)
        await api._get_items(url=url, id_list=id_list_reduced, key=key, limit=api_mock.limit_upper - 50)
        await api._get_items(url=url, id_list=id_list, key=key, limit=api_mock.limit_upper + 50)
        await api._get_items(url=url, id_list=id_list, key=key, limit=valid_limit)

        for url, _, _ in await api_mock.get_requests(url=url):
            count = len(unquote(url.query["ids"]).split(","))
            assert count >= 1
            assert count <= api_mock.limit_max

    ###########################################################################
    ## Input validation
    ###########################################################################
    @pytest.mark.parametrize("object_type", [Resource.ALBUM], ids=idfn)
    async def test_extend_items_input_validation(
            self,
            object_type: Resource,
            response: dict[str, Any],
            key: str,
            api: SpotifyAPI,
            api_mock: SpotifyMock
    ):
        # function should skip on fully extended response
        while len(response[key][api.items_key]) < response[key]["total"]:
            response[key][api.items_key].append(choice(response[key][api.items_key]))

        await api.extend_items(response, kind=object_type, key=api.collection_item_map[object_type])
        api_mock.assert_not_called()

    async def test_get_user_items_input_validation(self, api: SpotifyAPI):
        # raises error when invalid item type given
        for kind in set(ALL_ITEM_TYPES) - api.user_item_types:
            with pytest.raises(RemoteObjectTypeError):
                await api.get_user_items(kind=kind)

        # may only get valid user item types that are not playlists from the currently authorised user
        for kind in api.user_item_types - {Resource.PLAYLIST}:
            with pytest.raises(RemoteObjectTypeError):
                await api.get_user_items(user=random_str(1, RemoteIDType.ID.value - 1), kind=kind)

    async def test_extend_tracks_input_validation(self, api: SpotifyAPI):
        assert await api.extend_tracks(values=random_ids(), features=False, analysis=False) == []
        assert await api.extend_tracks(values=[], features=True, analysis=True) == []

        value = api.wrangler.convert(
            random_id(), kind=Resource.ALBUM, type_in=RemoteIDType.ID, type_out=RemoteIDType.URL
        )
        with pytest.raises(RemoteObjectTypeError):
            await api.extend_tracks(values=value, features=True)

    async def test_get_artist_albums_input_validation(self, api: SpotifyAPI):
        assert await api.get_artist_albums(values=[]) == {}

        value = api.wrangler.convert(
            random_id(), kind=Resource.ALBUM, type_in=RemoteIDType.ID, type_out=RemoteIDType.URL
        )
        with pytest.raises(RemoteObjectTypeError):
            await api.get_artist_albums(values=value)

        with pytest.raises(APIError):
            await api.get_artist_albums(values=random_id(), types=("unknown", "invalid"))

    ###########################################################################
    ## Multi-, Batched-, and Extend tests for each supported item type
    ###########################################################################
    async def test_get_items_multi(
            self,
            object_type: Resource,
            responses: dict[str, dict[str, Any]],
            api: SpotifyAPI,
            api_mock: SpotifyMock
    ):
        url = f"{api.url}/{object_type.name.lower()}s"
        params = {"key": "value"}

        results = await api._get_items(url=url, id_list=responses, params=params, key=None, limit=1)
        requests = [url for url, _, _ in await api_mock.get_requests(url=url)]

        self.assert_item_types(results=results, key=object_type.name.lower())
        self.assert_get_items_results(results=results, expected=responses, object_type=object_type)
        self.assert_params(requests=requests, params=params)

        # appropriate number of requests were made for multi requests
        requests = [req for id_ in responses for req in await api_mock.get_requests(url=f"{url}/{id_}")]
        assert len(requests) == len(responses)

    @pytest.mark.parametrize("object_type", [
        Resource.TRACK,
        Resource.ALBUM,
        Resource.ARTIST,
        Resource.SHOW,
        Resource.EPISODE,
        Resource.AUDIOBOOK,
        Resource.CHAPTER,
    ], ids=idfn)
    async def test_get_items_batched(
            self,
            object_type: Resource,
            responses: dict[str, dict[str, Any]],
            api: SpotifyAPI,
            api_mock: SpotifyMock
    ):
        key = object_type.name.lower() + "s"
        url = f"{api.url}/{key}"
        params = {"key": "value"}
        limit = get_limit(responses, max_limit=api_mock.limit_max, pages=3)
        assert limit > 1

        results = await api._get_items(url=url, id_list=responses, params=params, key=key, limit=limit)
        requests = [url for url, _, _ in await api_mock.get_requests(url=url)]

        self.assert_item_types(results=results, key=object_type.name.lower())
        self.assert_get_items_results(results=results, expected=responses, object_type=object_type)
        self.assert_params(requests=requests, params=[params])

        # appropriate number of requests were made for batched requests
        id_params = [{"ids": ",".join(ids)} for ids in batched(responses, limit)]
        requests = [url for url in requests if "ids" in url.query]
        assert len(requests) == len(id_params) < len(results)
        self.assert_params(requests=requests, params=id_params)

    @pytest.mark.parametrize("object_type", [
        Resource.PLAYLIST, Resource.ALBUM,  Resource.SHOW, Resource.AUDIOBOOK,
    ], ids=idfn)
    async def test_extend_items(
            self,
            object_type: Resource,
            response: dict[str, Any],
            key: str,
            api: SpotifyAPI,
            api_mock: SpotifyMock
    ):
        total = response[key]["total"]
        limit = self.reduce_items(response=response, key=key, api=api, api_mock=api_mock)
        items = response[key][api.items_key]

        results = await api.extend_items(
            response=response, kind=object_type, key=api.collection_item_map.get(object_type, object_type)
        )

        # assert extension to total
        assert len(results) == total
        assert len(items) == total
        assert items == results  # extension happened to input value and results match input
        self.assert_item_types(results=items, object_type=object_type, key=key)

        # appropriate number of requests made (minus 1 for initial input)
        requests = await api_mock.get_requests(url=URL(response[key][self.url_key]).with_query(None))
        assert len(requests) == api_mock.calculate_pages(limit=limit, total=total) - 1

        self.assert_response_enriched_with_parent(object_type=object_type, key=key, response=response)

    @pytest.mark.parametrize("object_type", [
        Resource.PLAYLIST, Resource.ALBUM,
        # RemoteObjectType.SHOW, RemoteObjectType.AUDIOBOOK,  RemoteResponse types not yet implemented for these
    ], ids=idfn)
    async def test_extend_items_on_response(
            self,
            object_type: Resource,
            response: dict[str, Any],
            key: str,
            api: SpotifyAPI,
            api_mock: SpotifyMock,
            object_factory: SpotifyObjectFactory,
    ):
        self.reduce_items(response=response, key=key, api=api, api_mock=api_mock)
        original = object_factory[object_type](deepcopy(response), skip_checks=True)
        test = object_factory[object_type](response, skip_checks=True)

        await api.extend_items(response=test, key=api.collection_item_map.get(object_type, object_type))
        test.refresh()

        self.assert_response_extended(actual=test, expected=original)

    # noinspection PyTestUnpassedFixture
    @pytest.mark.parametrize("object_type", [
        Resource.PLAYLIST, Resource.ALBUM, Resource.SHOW, Resource.AUDIOBOOK
    ], ids=idfn)
    async def test_extend_items_caches(
            self,
            object_type: Resource,
            response: dict[str, Any],
            key: str,
            api_cache: SpotifyAPI,
            api_mock: SpotifyMock
    ):
        self.reduce_items(response=response, key=key, api=api_cache, api_mock=api_mock)
        method = "GET"
        response = response[key]

        if object_type == Resource.PLAYLIST:
            url = response[api_cache.items_key][0][key.rstrip("s")][self.url_key]
        else:
            url = response[api_cache.items_key][0][self.url_key]
        repository = api_cache.handler.session.cache.get_repository_from_url(url=url)
        await repository.clear()

        items = [
            item if object_type != Resource.PLAYLIST else item[key.rstrip("s")]
            for item in response[api_cache.items_key]
        ]
        id_list = [item[self.id_key] for item in items]

        assert any([not await repository.contains((method, id_)) for id_ in id_list])
        await api_cache.extend_items(response=response, key=api_cache.collection_item_map.get(object_type, object_type))
        assert all([await repository.contains((method, id_)) for id_ in id_list])

    ###########################################################################
    ## ``get_user_items``
    ###########################################################################
    @pytest.mark.parametrize("object_type,user", [
        (Resource.PLAYLIST, False),
        (Resource.PLAYLIST, True),
        (Resource.TRACK, False),
        (Resource.ALBUM, False),
        (Resource.ARTIST, False),
        (Resource.SHOW, False),
        (Resource.EPISODE, False),
        (Resource.AUDIOBOOK, False),
    ], ids=idfn)
    async def test_get_user_items(
            self,
            object_type: Resource,
            user: bool,
            api: SpotifyAPI,
            api_mock: SpotifyMock
    ):
        test = None
        if user:
            test = random_id_type(id_=api_mock.user_id, wrangler=api.wrangler, kind=Resource.USER)
            url = f"{api.url}/users/{api_mock.user_id}/{object_type.name.lower()}s"
        elif object_type == Resource.ARTIST:
            url = f"{api.url}/me/following"
        else:
            url = f"{api.url}/me/{object_type.name.lower()}s"

        responses = {
            response[self.id_key] if self.id_key in response else response[object_type.name.lower()][self.id_key]:
                deepcopy(response)
            for response in api_mock.item_type_map_user[object_type]
        }
        if object_type == Resource.PLAYLIST:  # ensure items block is reduced for playlist responses as expected
            for response in responses.values():
                response["tracks"] = {
                    self.url_key: response["tracks"][self.url_key],
                    "total": response["tracks"]["total"]
                }

        total = len(responses)
        limit = get_limit(total, max_limit=api_mock.limit_max, pages=3)

        results = await api.get_user_items(user=test, kind=object_type, limit=limit)
        assert len(results) == total

        # appropriate number of requests made
        requests = await api_mock.get_requests(url=url)
        assert len(requests) == api_mock.calculate_pages(limit=limit, total=total)

        for result in results:  # check results are as expected
            if object_type not in {Resource.PLAYLIST, Resource.ARTIST}:
                assert "added_at" in result
                result = result[object_type.name.lower()]
                assert result == responses[result[self.id_key]][object_type.name.lower()]
            else:
                assert result == responses[result[self.id_key]]

    ###########################################################################
    ## ``get_items`` - tests
    ###########################################################################
    update_keys = {
        Resource.PLAYLIST: {"description", "followers", "images", "public"},
        Resource.TRACK: {"artists", "album"},
        Resource.ALBUM: {"artists", "copyrights", "external_ids", "genres", "label", "popularity", "tracks"},
        Resource.ARTIST: {"followers", "genres", "images", "popularity"},
        Resource.USER: {"display_name", "followers", "images", "product"},
        Resource.SHOW: {"copyrights", "images", "languages", "episodes"},
        Resource.EPISODE: {"language", "images", "languages", "show"},
        Resource.AUDIOBOOK: {"copyrights", "edition", "languages", "images", "chapters"},
        Resource.CHAPTER: {"languages", "images", "chapters"},
    }

    async def test_get_items_single_string(
            self,
            object_type: Resource,
            response: dict[str, Any],
            extend: bool,
            key: str,
            api: SpotifyAPI,
            api_mock: SpotifyMock
    ):
        results = await api.get_items(
            values=random_id_type(id_=response[self.id_key], wrangler=api.wrangler, kind=object_type),
            kind=object_type,
            extend=extend
        )
        self.assert_item_types(results=results, key=object_type.name.lower())
        self.assert_get_items_results(
            results=results, expected={response[self.id_key]: response}, object_type=object_type, key=key
        )
        await self.assert_get_items_calls(
            responses=[response], object_type=object_type, key=key, api=api, api_mock=api_mock
        )

        # just check that these don't fail
        await api.get_items(values=response["uri"])
        await api.get_items(values=response[self.url_key])
        await api.get_items(values=response["external_urls"]["spotify"])

    async def test_get_items_many_string(
            self,
            object_type: Resource,
            responses: dict[str, dict[str, Any]],
            extend: bool,
            key: str,
            api: SpotifyAPI,
            api_mock: SpotifyMock
    ):
        limit = None
        if object_type not in {Resource.PLAYLIST, Resource.USER}:
            limit = get_limit(responses, max_limit=api_mock.limit_max)
            assert len(responses) > limit

        results = await api.get_items(
            values=random_id_types(id_list=responses, wrangler=api.wrangler, kind=object_type),
            kind=object_type,
            limit=limit or api_mock.limit_max,
            extend=extend
        )
        self.assert_item_types(results=results, key=object_type.name.lower())
        self.assert_get_items_results(results=results, expected=responses, object_type=object_type, key=key)
        await self.assert_get_items_calls(
            responses=responses.values(), object_type=object_type, key=key, limit=limit, api=api, api_mock=api_mock
        )

    async def test_get_items_single_mapping(
            self,
            object_type: Resource,
            response: dict[str, Any],
            key: str,
            api: SpotifyAPI,
    ):
        test = {k: v for k, v in response.items() if k not in self.update_keys[object_type]}
        self.assert_different(response, test, key)

        results = await api.get_items(values=test)
        self.assert_item_types(results=results, key=object_type.name.lower())
        self.assert_get_items_results(
            results=results,
            expected={response[self.id_key]: response},
            test={test[self.id_key]: test},
            key=key,
            object_type=object_type
        )

    async def test_get_items_many_mapping(
            self,
            object_type: Resource,
            responses: dict[str, dict[str, Any]],
            key: str,
            api: SpotifyAPI,
    ):
        # test input maps are updated when API responses are given
        test = {
            id_: {k: v for k, v in response.items() if k not in self.update_keys[object_type]}
            for id_, response in responses.items()
        }
        for response in responses.values():
            self.assert_different(response, test[response[self.id_key]], key)

        results = await api.get_items(values=test.values())
        self.assert_item_types(results=results, key=object_type.name.lower())
        self.assert_get_items_results(results=results, expected=responses, test=test, key=key, object_type=object_type)

    @pytest.mark.parametrize("object_type", [
        Resource.TRACK, Resource.PLAYLIST, Resource.ALBUM,
        # other RemoteResponse types not yet implemented/do not provide expected results
    ], ids=idfn)
    async def test_get_items_single_response(
            self,
            object_type: Resource,
            response: dict[str, Any],
            key: str,
            api: SpotifyAPI,
            api_mock: SpotifyMock,
            object_factory: SpotifyObjectFactory,
    ):
        if object_type in api.collection_item_map:
            self.reduce_items(response=response, key=key, api=api, api_mock=api_mock)

        factory = object_factory[object_type]
        original = factory(deepcopy(response), skip_checks=True)
        test = factory({k: v for k, v in response.items() if k not in self.update_keys[object_type]}, skip_checks=True)
        self.assert_different(original.response, test.response, key)

        results = await api.get_items(values=test)
        self.assert_get_items_results(
            results=results,
            expected={original.id: original.response},
            test={test.id: test.response},
            key=key,
            object_type=object_type
        )

        if object_type in api.collection_item_map:
            self.assert_response_extended(actual=test, expected=original)

    # noinspection PyTestUnpassedFixture
    @pytest.mark.parametrize("object_type", [
        Resource.TRACK, Resource.PLAYLIST, Resource.ALBUM,
        # other RemoteResponse types not yet implemented/do not provide expected results
    ], ids=idfn)
    async def test_get_items_many_response(
            self,
            object_type: Resource,
            responses: dict[str, dict[str, Any]],
            key: str,
            api: SpotifyAPI,
            api_mock: SpotifyMock,
            object_factory: SpotifyObjectFactory,
    ):
        if object_type in api.collection_item_map:
            for id_, response in responses.items():
                self.reduce_items(response=response, key=key, api=api, api_mock=api_mock)

        factory = object_factory[object_type]
        original = [factory(deepcopy(response), skip_checks=True) for response in responses.values()]
        test = [
            factory({k: v for k, v in response.items() if k not in self.update_keys[object_type]}, skip_checks=True)
            for response in responses.values()
        ]
        for orig, ts in zip(original, test, strict=True):
            self.assert_different(orig.response, ts.response, key)

        results = await api.get_items(values=test)
        self.assert_get_items_results(
            results=results,
            expected={response.id: response.response for response in original},
            test={response.id: response.response for response in test},
            key=key,
            object_type=object_type
        )
        if object_type in api.collection_item_map:
            for orig, ts in zip(original, test, strict=True):
                self.assert_response_extended(actual=ts, expected=orig)

    ###########################################################################
    ## ``extend_tracks`` tests
    ###########################################################################
    @pytest.fixture
    def features_all(self, responses: dict[str, dict[str, Any]], api_mock: SpotifyMock) -> dict[str, dict[str, Any]]:
        """Yield all audio features responses for the given ``responses`` as a pytest.fixture."""
        for response in responses:
            assert "audio_features" not in response
        return {id_: deepcopy(api_mock.audio_features[id_]) for id_ in responses if id_ in api_mock.audio_features}

    @pytest.fixture
    def features(self, response: dict[str, Any], features_all: dict[str, dict[str, Any]]) -> dict[str, Any]:
        """Yield the audio features  response for the given ``response`` as a pytest.fixture."""
        assert "audio_features" not in response
        return features_all[response[self.id_key]]

    @pytest.fixture
    def analysis_all(self, responses: dict[str, dict[str, Any]], api_mock: SpotifyMock) -> dict[str, dict[str, Any]]:
        """Yield all audio analyses responses for the given ``responses`` as a pytest.fixture."""
        for response in responses:
            assert "audio_analysis" not in response
        return {id_: deepcopy(api_mock.audio_analysis[id_]) for id_ in responses if id_ in api_mock.audio_analysis}

    @pytest.fixture
    def analysis(self, response: dict[str, Any], analysis_all: dict[str, dict[str, Any]]) -> dict[str, Any]:
        """Yield all audio analysis response for the given ``response`` as a pytest.fixture."""
        assert "audio_analysis" not in response
        return analysis_all[response[self.id_key]]

    def assert_extend_tracks_results(
            self,
            results: list[dict[str, Any]],
            test: dict[str, dict[str, Any]] | None = None,
            features: dict[str, dict[str, Any]] | None = None,
            features_in_results: bool = True,
            analysis: dict[str, dict[str, Any]] | None = None,
            analysis_in_results: bool = True,
    ):
        """
        Check the results contain the appropriate keys and values after running ``extend_tracks`` related methods.
        """
        if test:
            assert len(results) == len(test)

        for result in results:
            self._assert_extend_tracks_result(
                result=result,
                key="audio_features",
                test=test,
                extension=features[result[self.id_key]] if features else None,
                extension_in_results=features_in_results
            )
            self._assert_extend_tracks_result(
                result=result,
                key="audio_analysis",
                test=test,
                extension=analysis[result[self.id_key]] | {self.id_key: result[self.id_key]} if analysis else None,
                extension_in_results=analysis_in_results
            )

    def _assert_extend_tracks_result(
            self,
            result: dict[str, Any],
            key: str,
            test: dict[str, dict[str, Any]] | None = None,
            extension: dict[str, Any] | None = None,
            extension_in_results: bool = True,
    ):
        if extension:
            if extension_in_results:
                result[key].pop("href", None)
                assert result[key] == extension
            else:
                assert key not in result

            if test:
                assert test[result[self.id_key]][key] == extension
        else:
            assert key not in result
            if test:
                assert key not in test[result[self.id_key]]

    async def assert_extend_tracks_calls(
            self,
            responses: Collection[dict[str, Any]],
            api: SpotifyAPI,
            api_mock: SpotifyMock,
            features: bool = True,
            analysis: bool = True,
            limit: int = 1,
    ):
        """Assert appropriate number of requests made for extend_tracks method calls"""
        requests = []
        if features and limit > 1:
            requests += await api_mock.get_requests(url=f"{api.url}/audio-features")
        if analysis and limit > 1:
            requests += await api_mock.get_requests(url=f"{api.url}/audio-analysis")

        for response in responses:
            if features:
                requests += await api_mock.get_requests(url=f"{api.url}/audio-features/{response[self.id_key]}")
            if analysis:
                requests += await api_mock.get_requests(url=f"{api.url}/audio-analysis/{response[self.id_key]}")

        assert len(requests) == len(list(batched(responses, limit))) + len(responses)

    @pytest.mark.parametrize("object_type", [Resource.TRACK], ids=idfn)
    async def test_extend_tracks_single_string(
            self,
            object_type: Resource,
            response: dict[str, Any],
            features: dict[str, Any],
            analysis: dict[str, Any],
            api: SpotifyAPI,
            api_mock: SpotifyMock
    ):
        results = await api.extend_tracks(
            values=random_id_type(id_=response[self.id_key], wrangler=api.wrangler, kind=Resource.TRACK),
            features=True,
            analysis=True
        )

        assert len(results) == 1
        self.assert_extend_tracks_results(
            results=results, features={response[self.id_key]: features}, analysis={response[self.id_key]: analysis}
        )
        await self.assert_extend_tracks_calls(
            responses=[response], features=True, analysis=True, api=api, api_mock=api_mock
        )

        # just check that these don't fail
        await api.extend_tracks(values=response["uri"])
        await api.extend_tracks(values=response[self.url_key])
        await api.extend_tracks(values=response["external_urls"]["spotify"])

    @pytest.mark.parametrize("object_type", [Resource.TRACK], ids=idfn)
    async def test_extend_tracks_many_string(
            self,
            object_type: Resource,
            responses: dict[str, Any],
            features_all: dict[str, dict[str, Any]],
            analysis_all: dict[str, dict[str, Any]],
            api: SpotifyAPI,
            api_mock: SpotifyMock,
    ):
        limit = get_limit(responses, max_limit=api_mock.limit_max)
        test = random_id_types(id_list=responses, wrangler=api.wrangler, kind=Resource.TRACK)

        results = await api.extend_tracks(values=test, features=True, analysis=True, limit=limit)

        self.assert_extend_tracks_results(results=results, features=features_all, analysis=analysis_all)
        await self.assert_extend_tracks_calls(
            responses=responses.values(), features=True, analysis=True, api=api, api_mock=api_mock, limit=limit
        )

    @pytest.mark.parametrize("object_type", [Resource.TRACK], ids=idfn)
    async def test_extend_tracks_single_mapping(
            self,
            object_type: Resource,
            response: dict[str, Any],
            features: dict[str, Any],
            analysis: dict[str, Any],
            api: SpotifyAPI,
    ):
        results = await api.extend_tracks(values=response, features=True, analysis=False)
        self.assert_extend_tracks_results(
            results=results, test={response[self.id_key]: response}, features={response[self.id_key]: features},
        )

        results = await api.extend_tracks(values=response, features=False, analysis=True)
        self.assert_extend_tracks_results(
            results=results,
            test={response[self.id_key]: response},
            features={response[self.id_key]: features},
            features_in_results=False,
            analysis={response[self.id_key]: analysis},
        )

    @pytest.mark.parametrize("object_type", [Resource.TRACK], ids=idfn)
    async def test_extend_tracks_many_mapping(
            self,
            object_type: Resource,
            responses: dict[str, Any],
            features_all: dict[str, dict[str, Any]],
            analysis_all: dict[str, dict[str, Any]],
            api: SpotifyAPI,
            api_mock: SpotifyMock,
    ):
        results = await api.extend_tracks(values=responses.values(), features=True, analysis=False)
        self.assert_extend_tracks_results(results=results, test=responses, features=features_all)

        results = await api.extend_tracks(values=responses.values(), features=False, analysis=True)
        self.assert_extend_tracks_results(
            results=results, test=responses, features=features_all, features_in_results=False, analysis=analysis_all,
        )

    @pytest.mark.parametrize("object_type", [Resource.TRACK], ids=idfn)
    async def test_extend_tracks_single_response(
            self,
            object_type: Resource,
            response: dict[str, Any],
            key: str,
            features: dict[str, Any],
            analysis: dict[str, Any],
            api: SpotifyAPI,
            api_mock: SpotifyMock,
            object_factory: SpotifyObjectFactory,
    ):
        # noinspection PyTypeChecker
        test: SpotifyTrack = object_factory[object_type](response, skip_checks=True)
        assert test.bpm is None

        results = await api.extend_tracks(values=response, features=True, analysis=False)
        self.assert_extend_tracks_results(results=results, test={test.id: test.response}, features={test.id: features})
        assert test.bpm is not None

        results = await api.extend_tracks(values=response, features=False, analysis=True)
        self.assert_extend_tracks_results(
            results=results,
            test={test.id: test.response},
            features={test.id: features},
            features_in_results=False,
            analysis={test.id: analysis},
        )
        assert test.bpm is not None

    @pytest.mark.parametrize("object_type", [Resource.TRACK], ids=idfn)
    async def test_extend_tracks_many_response(
            self,
            object_type: Resource,
            responses: dict[str, dict[str, Any]],
            key: str,
            features_all: dict[str, dict[str, Any]],
            analysis_all: dict[str, dict[str, Any]],
            api: SpotifyAPI,
            api_mock: SpotifyMock,
            object_factory: SpotifyObjectFactory,
    ):
        factory = object_factory[object_type]
        # noinspection PyTypeChecker
        test: list[SpotifyTrack] = [factory(response, skip_checks=True) for response in responses.values()]
        for t in test:
            assert t.bpm is None

        results = await api.extend_tracks(values=responses.values(), features=True, analysis=False)
        self.assert_extend_tracks_results(results=results, test=responses, features=features_all)
        for t in test:
            assert t.bpm is not None

        results = await api.extend_tracks(values=responses.values(), features=False, analysis=True)
        self.assert_extend_tracks_results(
            results=results, test=responses, features=features_all, features_in_results=False, analysis=analysis_all,
        )

    @pytest.mark.parametrize("object_type", [Resource.TRACK], ids=idfn)
    async def test_get_tracks(
            self,
            object_type: Resource,
            response: dict[str, Any],
            api_cache: SpotifyAPI,
            api_mock: SpotifyMock,
            object_factory: SpotifyObjectFactory,
    ):
        results = await api_cache.get_tracks(
            values=random_id_type(id_=response[self.id_key], wrangler=api_cache.wrangler, kind=Resource.TRACK),
            features=True,
            analysis=True
        )
        self.assert_similar(response, results[0], "audio_features", "audio_analysis")
        assert "audio_features" not in response
        assert "audio_analysis" not in response

        test_response = deepcopy(response)
        results = await api_cache.get_tracks(values=test_response, features=True, analysis=True)
        assert results[0] == test_response
        assert "audio_features" in test_response
        assert "audio_analysis" in test_response

        # noinspection PyTypeChecker
        test_object: SpotifyTrack = object_factory[object_type](response, skip_checks=True)
        assert test_object.bpm is None

        await api_cache.get_tracks(values=response, features=True, analysis=True)
        assert "audio_features" in response
        assert "audio_analysis" in response
        assert test_object.bpm is not None
