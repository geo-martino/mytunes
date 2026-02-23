from copy import deepcopy
from random import randrange, sample
from typing import Any

import pytest
from aiorequestful.types import URLInput
from aioresponses.core import RequestCall
from yarl import URL

from musify import PROGRAM_NAME
from musify._types import Resource
from musify.libraries.remote.core.exception import RemoteObjectTypeError, RemoteIDTypeError
from musify.libraries.remote.core.types import RemoteIDType
from musify.libraries.remote.spotify.api import SpotifyAPI
from musify.libraries.remote.spotify.object import SpotifyPlaylist
from tests.libraries.remote.core.api import RemoteAPIPlaylistTester
from tests.libraries.remote.core.utils import ALL_ITEM_TYPES
from tests.libraries.remote.spotify.api.mock import SpotifyMock
from tests.libraries.remote.spotify.utils import random_ids, random_id, random_id_type, random_id_types
from tests.libraries.remote.spotify.utils import random_uris, random_api_urls, random_ext_urls


class TestSpotifyAPIPlaylists(RemoteAPIPlaylistTester):
    """Tester for playlist modification type endpoints of :py:class:`SpotifyAPI`"""

    @staticmethod
    @pytest.fixture
    def playlist(api_mock: SpotifyMock) -> dict[str, Any]:
        """Yields a response representing a user playlist on Spotify"""
        return next(deepcopy(pl) for pl in api_mock.user_playlists if pl["tracks"]["total"] > api_mock.limit_lower)

    @staticmethod
    @pytest.fixture
    def playlist_unique(api_mock: SpotifyMock) -> dict[str, Any]:
        """Yields a response representing a uniquely named user playlist on Spotify"""
        names = [pl["name"] for pl in api_mock.user_playlists]
        return next(
            deepcopy(pl) for pl in api_mock.user_playlists
            if names.count(pl["name"]) == 1 and len(pl["name"]) != RemoteIDType.ID.value
        )

    @staticmethod
    def _get_payload_from_request(request: RequestCall) -> dict[str, Any] | None:
        return request.kwargs.get("body", request.kwargs.get("json"))

    @classmethod
    async def _get_payloads_from_url_base(cls, url: URLInput, api_mock: SpotifyMock) -> list[dict[str, Any]]:
        return [
            cls._get_payload_from_request(req) for _, req, _ in await api_mock.get_requests(url=url)
            if cls._get_payload_from_request(req)
        ]

    ###########################################################################
    ## Basic functionality
    ###########################################################################
    async def test_get_playlist_url(self, playlist_unique: dict[str, Any], api: SpotifyAPI, api_mock: SpotifyMock):
        assert await api.get_playlist_url(playlist=playlist_unique) == URL(playlist_unique["href"])
        assert await api.get_playlist_url(playlist=playlist_unique["name"]) == URL(playlist_unique["href"])
        pl_object = SpotifyPlaylist(playlist_unique, skip_checks=True)
        assert await api.get_playlist_url(playlist=pl_object) == URL(playlist_unique["href"])

        with pytest.raises(RemoteIDTypeError):
            await api.get_playlist_url("does not exist")

    ###########################################################################
    ## POST playlist operations
    ###########################################################################
    async def test_create_playlist(self, api: SpotifyAPI, api_mock: SpotifyMock):
        name = "test playlist"
        url = f"{api.url}/users/{api_mock.user_id}/playlists"
        result = await api.create_playlist(name=name, public=False, collaborative=True)

        _, _, response = next(iter(await api_mock.get_requests(url=url, response={"name": name})))
        body = await response.json()
        assert body["name"] == result["name"] == name
        assert PROGRAM_NAME in body["description"] and PROGRAM_NAME in result["description"]
        assert not body["public"] and not result["public"]
        assert body["collaborative"] and result["collaborative"]
        assert result[api.url_key].removeprefix(f"{api.url}/playlists/").strip("/")

        assert result["owner"]["display_name"] == api.user_name
        assert result["owner"][api.id_key] == api.user_id
        assert api.user_id in result["owner"]["uri"]
        assert api.user_id in result["owner"][api.url_key]
        assert api.user_id in result["owner"]["external_urls"][api.source.lower()]

    async def test_add_to_playlist_input_validation_and_skips(self, api: SpotifyAPI, api_mock: SpotifyMock):
        url = f"{api.url}/playlists/{random_id()}"
        for kind in ALL_ITEM_TYPES:
            if kind == Resource.TRACK:
                continue

            with pytest.raises(RemoteObjectTypeError):
                await api.add_to_playlist(playlist=url, items=random_uris(kind=kind))

            with pytest.raises(RemoteObjectTypeError):
                await api.add_to_playlist(playlist=url, items=random_api_urls(kind=kind))

            with pytest.raises(RemoteObjectTypeError):
                await api.add_to_playlist(playlist=url, items=random_ext_urls(kind=kind))

        assert await api.add_to_playlist(playlist=url, items=()) == 0

        with pytest.raises(RemoteIDTypeError):
            await api.add_to_playlist(playlist="does not exist", items=random_ids())

    async def test_add_to_playlist_batches_limited(
            self, playlist: dict[str, Any], api: SpotifyAPI, api_mock: SpotifyMock
    ):
        id_list = random_ids(200, 300)
        valid_limit = 80

        await api.add_to_playlist(playlist=playlist["href"], items=sample(id_list, k=10), limit=-30, skip_dupes=False)
        await api.add_to_playlist(playlist=playlist["href"], items=id_list, limit=200, skip_dupes=False)
        await api.add_to_playlist(playlist=playlist["href"], items=id_list, limit=valid_limit, skip_dupes=False)

        requests = await api_mock.get_requests(url=playlist["href"] + "/tracks")

        for i, (_, request, _) in enumerate(requests, 1):
            payload = self._get_payload_from_request(request)
            count = len(payload["uris"])
            assert count >= 1
            assert count <= 100

    async def test_add_to_playlist(self, playlist: dict[str, Any], api: SpotifyAPI, api_mock: SpotifyMock):
        total = playlist["tracks"]["total"]
        limit = total // 3
        assert total > limit  # ensure ranges are valid for test to work

        id_list = random_id_types(
            wrangler=api.wrangler, kind=Resource.TRACK, start=total - api_mock.limit_lower, stop=total - 1
        )
        assert len(id_list) < total

        result = await api.add_to_playlist(playlist=playlist["id"], items=id_list, limit=limit, skip_dupes=False)
        assert result == len(id_list)

        uris = []
        for _, request, _ in await api_mock.get_requests(url=playlist["href"] + "/tracks"):
            payload = self._get_payload_from_request(request)
            if "uris" in payload:
                uris.extend(payload["uris"])
        assert len(uris) == len(id_list)

        # check same results for other input types
        result = await api.add_to_playlist(playlist=playlist, items=id_list, limit=limit, skip_dupes=False)
        assert result == len(id_list)

        pl = SpotifyPlaylist(playlist, skip_checks=True)
        result = await api.add_to_playlist(playlist=pl, items=id_list, limit=limit, skip_dupes=False)
        assert result == len(id_list)

    async def test_add_to_playlist_with_skip(self, playlist: dict[str, Any], api: SpotifyAPI, api_mock: SpotifyMock):
        await api.extend_items(playlist["tracks"])

        initial = len(playlist["tracks"]["items"])
        total = playlist["tracks"]["total"]
        limit = total // 3
        assert total > limit  # ensure ranges are valid for test to work

        source = sample(playlist["tracks"]["items"], k=randrange(start=initial // 3, stop=initial // 2))
        id_list_dupes = [item["track"]["id"] for item in source]
        id_list_new = random_id_types(
            wrangler=api.wrangler, kind=Resource.TRACK, start=api_mock.limit_lower, stop=randrange(20, 30)
        )

        result = await api.add_to_playlist(playlist=playlist["uri"], items=id_list_dupes + id_list_new, limit=limit)
        assert result == len(id_list_new)

        uris = []
        for _, request, _ in await api_mock.get_requests(url=playlist["href"] + "/tracks"):
            payload = self._get_payload_from_request(request)
            if payload and "uris" in payload:
                uris.extend(payload["uris"])
        assert len(uris) == len(id_list_new)

    ###########################################################################
    ## PUT playlist operations
    ###########################################################################
    async def test_follow_playlist(self, playlist_unique: dict[str, Any], api: SpotifyAPI, api_mock: SpotifyMock):
        result = await api.follow_playlist(
            random_id_type(id_=playlist_unique["id"], wrangler=api.wrangler, kind=Resource.PLAYLIST)
        )
        assert result == URL(playlist_unique["href"] + "/followers")

        result = await api.follow_playlist(playlist_unique)
        assert result == URL(playlist_unique["href"] + "/followers")

        result = await api.follow_playlist(SpotifyPlaylist(playlist_unique, skip_checks=True))
        assert result == URL(playlist_unique["href"] + "/followers")

    ###########################################################################
    ## DELETE playlist operations
    ###########################################################################
    async def test_delete_playlist(self, playlist_unique: dict[str, Any], api: SpotifyAPI, api_mock: SpotifyMock):
        result = await api.delete_playlist(
            random_id_type(id_=playlist_unique["id"], wrangler=api.wrangler, kind=Resource.PLAYLIST)
        )
        assert result == URL(playlist_unique["href"] + "/followers")

        result = await api.delete_playlist(playlist_unique)
        assert result == URL(playlist_unique["href"] + "/followers")

        result = await api.delete_playlist(SpotifyPlaylist(playlist_unique, skip_checks=True))
        assert result == URL(playlist_unique["href"] + "/followers")

    async def test_clear_from_playlist_input_validation_and_skips(self, api: SpotifyAPI, api_mock: SpotifyMock):
        url = f"{api.url}/playlists/{random_id()}"
        for kind in ALL_ITEM_TYPES:
            if kind == Resource.TRACK:
                continue

            with pytest.raises(RemoteObjectTypeError):
                await api.clear_from_playlist(playlist=url, items=random_uris(kind=kind))

            with pytest.raises(RemoteObjectTypeError):
                await api.clear_from_playlist(playlist=url, items=random_api_urls(kind=kind))

            with pytest.raises(RemoteObjectTypeError):
                await api.clear_from_playlist(playlist=url, items=random_ext_urls(kind=kind))

        result = await api.clear_from_playlist(playlist=url, items=())
        assert result == 0

        with pytest.raises(RemoteIDTypeError):
            await api.add_to_playlist(playlist="does not exist", items=random_ids())

    async def test_clear_from_playlist_batches_limited(
            self, playlist: dict[str, Any], api: SpotifyAPI, api_mock: SpotifyMock
    ):
        id_list = random_ids(200, 300)
        valid_limit = 80

        await api.clear_from_playlist(playlist=playlist["href"], items=sample(id_list, k=10), limit=-30)
        await api.clear_from_playlist(playlist=playlist["href"], items=id_list, limit=valid_limit)
        await api.clear_from_playlist(playlist=playlist["href"], items=id_list, limit=200)

        requests = await self._get_payloads_from_url_base(url=playlist["href"] + "/tracks", api_mock=api_mock)
        for i, payload in enumerate(requests, 1):
            count = len(payload["tracks"])
            assert count >= 1
            assert count <= 100

    async def test_clear_from_playlist_items(self, playlist: dict[str, Any], api: SpotifyAPI, api_mock: SpotifyMock):
        total = playlist["tracks"]["total"]
        limit = total // 3
        assert total > limit  # ensure ranges are valid for test to work

        id_list = random_id_types(
            wrangler=api.wrangler, kind=Resource.TRACK, start=total - api_mock.limit_lower, stop=total - 1
        )
        assert len(id_list) < total

        result = await api.clear_from_playlist(playlist=playlist["uri"], items=id_list, limit=limit)
        assert result == len(id_list)

        requests = await self._get_payloads_from_url_base(url=playlist["href"] + "/tracks", api_mock=api_mock)
        assert all("tracks" in body for body in requests)
        assert sum(len(req["tracks"]) for req in requests) == len(id_list)

        # check same results for other input types
        result = await api.clear_from_playlist(playlist=playlist, items=id_list, limit=limit)
        assert result == len(id_list)

        pl = SpotifyPlaylist(playlist, skip_checks=True)
        result = await api.clear_from_playlist(playlist=pl, items=id_list, limit=limit)
        assert result == len(id_list)

    async def test_clear_from_playlist_all(self, playlist: dict[str, Any], api: SpotifyAPI, api_mock: SpotifyMock):
        total = playlist["tracks"]["total"]
        limit = total // 4
        assert total > limit  # ensure ranges are valid for test to work

        result = await api.clear_from_playlist(playlist=playlist, limit=limit)
        assert result == total

        requests = await self._get_payloads_from_url_base(url=playlist["href"] + "/tracks", api_mock=api_mock)
        assert all("tracks" in body for body in requests)
        assert sum(len(body["tracks"]) for body in requests) == total
