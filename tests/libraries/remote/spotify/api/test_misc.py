import re
from copy import deepcopy
from typing import Any
from urllib.parse import unquote

import pytest

from musify._types import Resource as ObjectType
from musify.libraries.remote.spotify.api import SpotifyAPI
from tests.conftest import LogCapturer
from tests.libraries.remote.spotify.api.mock import SpotifyMock
from tests.utils import idfn, random_str


class TestSpotifyAPIMisc:
    """Tester for miscellaneous endpoints of :py:class:`SpotifyAPI`"""

    @pytest.mark.parametrize("method_name,kwargs,floor,ceil", [
        ("query", {"query": "valid query", "kind": ObjectType.TRACK}, 1, 50),
        ("get_user_items", {"kind": ObjectType.PLAYLIST}, 1, 50)
    ], ids=idfn)
    async def test_limit_param_limited(
            self,
            method_name: str,
            kwargs: dict[str, Any],
            floor: int,
            ceil: int,
            api: SpotifyAPI,
            api_mock: SpotifyMock
    ):
        # too small
        await getattr(api, method_name)(limit=floor - 20, **kwargs)
        url, _, _ = next(reversed(await api_mock.get_requests()))
        assert "limit" in url.query
        assert int(url.query["limit"]) == floor

        # good value
        limit = floor + (ceil // 2)
        await getattr(api, method_name)(limit=limit, **kwargs)
        url, _, _ = next(reversed(await api_mock.get_requests()))
        assert "limit" in url.query
        assert int(url.query["limit"]) == limit

        # too big
        await getattr(api, method_name)(limit=ceil + 100, **kwargs)
        url, _, _ = next(reversed(await api_mock.get_requests()))
        assert "limit" in url.query
        assert int(url.query["limit"]) == ceil

    ###########################################################################
    ## /me + /search endpoints
    ###########################################################################
    async def test_get_self(self, api: SpotifyAPI, api_mock: SpotifyMock):
        api.user_data = {}
        assert await api.get_self(update_user_data=False) == api_mock.user
        assert api.user_data == {}

        assert await api.get_self(update_user_data=True) == api_mock.user
        assert api.user_data == api_mock.user

    async def test_query_input_validation(self, api: SpotifyAPI, api_mock: SpotifyMock):
        assert await api.query(query=None, kind=ObjectType.EPISODE) == []
        assert await api.query(query="", kind=ObjectType.SHOW) == []
        # long queries that would cause the API to give an error should fail safely
        assert await api.query(query=random_str(151, 200), kind=ObjectType.CHAPTER) == []

    @pytest.mark.parametrize("kind,query,limit", [
        (ObjectType.PLAYLIST, "super cool playlist", 5),
        (ObjectType.TRACK, "track 2", 10),
        (ObjectType.ALBUM, "best album title", 20),
        (ObjectType.ARTIST, "really cool artist name", 12),
        (ObjectType.SHOW, "amazing show", 17),
        (ObjectType.EPISODE, "incredible episode", 25),
        (ObjectType.AUDIOBOOK, "i love this audiobook", 6),
    ], ids=idfn)
    async def test_query(
            self,
            kind: ObjectType,
            query: str,
            limit: int,
            api: SpotifyAPI,
            api_mock: SpotifyMock,
    ):
        expected = api_mock.item_type_map[kind]
        results = await api.query(query=query, kind=kind, limit=limit)

        assert len(results) <= min(len(expected), limit)
        for result in results:
            assert result["type"] == kind.name.lower()

        url, _, _ = next(iter(await api_mock.get_requests(url=f"{api.url}/search", params={"q": query})))
        assert unquote(url.query["q"]) == query
        assert int(url.query["limit"]) == limit
        assert unquote(url.query["type"]) == kind.name.lower()

    ###########################################################################
    ## Utilities
    ###########################################################################
    @pytest.mark.parametrize("kind", [
        ObjectType.PLAYLIST, ObjectType.ALBUM,  ObjectType.SHOW, ObjectType.AUDIOBOOK,
    ], ids=idfn)
    async def test_pretty_print_uris(
            self,
            kind: ObjectType,
            api: SpotifyAPI,
            api_mock: SpotifyMock,
            log_capturer: LogCapturer,
            capfd: pytest.CaptureFixture
    ):
        key = api.collection_item_map.get(kind, kind).name.lower() + "s"
        source = deepcopy(next(item for item in api_mock.item_type_map[kind] if item[key]["total"] > 50))

        with log_capturer(loggers=api.logger):
            await api.print_collection(value=source)

        stdout = "\n".join(re.sub("\33.*?m", "", capfd.readouterr().out).strip().splitlines())

        # printed in blocks
        blocks = [block for block in stdout.split("\n\n\n")[-1].split("\n\n") if str(api_mock.url_ext) in block]
        assert len(blocks) == api_mock.total_requests

        # lines printed = total tracks + 1 extra for title
        lines = [line for line in log_capturer.text.split("\n") if str(api_mock.url_ext) in line]
        assert len(lines) == source[key]["total"] + 1
