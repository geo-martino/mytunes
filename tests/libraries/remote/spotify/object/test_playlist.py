from collections.abc import Iterable
from copy import deepcopy
from datetime import datetime
from random import randrange
from typing import Any

import pytest

from musify import PROGRAM_NAME
from musify.libraries.remote.core.exception import RemoteError, APIError, RemoteObjectTypeError
from musify.libraries.remote.core.types import RemoteObjectType
from musify.libraries.remote.spotify.api import SpotifyAPI
from musify.libraries.remote.spotify.exception import SpotifyCollectionError
from musify.libraries.remote.spotify.object import SpotifyPlaylist, SpotifyTrack
from tests.libraries.remote.core.object import RemotePlaylistTester
from tests.libraries.remote.spotify.api.mock import SpotifyMock
from tests.libraries.remote.spotify.object.testers import SpotifyCollectionLoaderTester
from tests.libraries.remote.spotify.utils import random_uri, assert_id_attributes


class TestSpotifyPlaylist(SpotifyCollectionLoaderTester, RemotePlaylistTester):

    @pytest.fixture
    def collection_merge_items(self, api_mock: SpotifyMock) -> Iterable[SpotifyTrack]:
        return [SpotifyTrack(api_mock.generate_track()) for _ in range(randrange(5, 10))]

    @pytest.fixture
    def item_kind(self, api: SpotifyAPI) -> RemoteObjectType:
        return api.collection_item_map[RemoteObjectType.PLAYLIST]

    @pytest.fixture
    def response_random(self, api_mock: SpotifyMock) -> dict[str, Any]:
        """Yield a randomly generated response from the Spotify API for a track item type"""
        response = api_mock.generate_playlist(item_count=100, use_stored=False)
        response["tracks"]["total"] = len(response["tracks"]["items"])
        response["tracks"]["next"] = None
        return response

    @pytest.fixture
    async def _response_valid(self, api: SpotifyAPI, api_mock: SpotifyMock) -> dict[str, Any]:
        response = next(
            deepcopy(pl) for pl in api_mock.user_playlists
            if pl["tracks"]["total"] > 50 and len(pl["tracks"]["items"]) > 10
        )
        await api.extend_items(response=response, key=RemoteObjectType.TRACK)

        api_mock.reset()  # reset for new requests checks to work correctly
        return response

    @pytest.fixture
    def response_valid(self, _response_valid: dict[str, Any]) -> dict[str, Any]:
        """
        Yield a valid enriched response with extended artists and albums responses
        from the Spotify API for a track item type. Just a deepcopy of _response_valid fixture.
        """
        return deepcopy(_response_valid)

    @pytest.fixture
    def playlist(self, response_valid: dict[str, Any], api: SpotifyAPI) -> SpotifyPlaylist:
        pl = SpotifyPlaylist(response=response_valid, api=api)
        pl._tracks = [item for item in pl.items if pl.items.count(item) == 1]
        return pl

    async def test_input_validation(self, response_random: dict[str, Any], api_mock: SpotifyMock):
        with pytest.raises(RemoteObjectTypeError):
            SpotifyPlaylist(api_mock.generate_album(track_count=0))
        with pytest.raises(APIError):
            await SpotifyPlaylist(response_random).reload()

        response_random["tracks"]["total"] += 10
        with pytest.raises(RemoteError):
            SpotifyPlaylist(response_random, skip_checks=False)
        response_random["tracks"]["total"] -= 20
        with pytest.raises(RemoteError):
            SpotifyPlaylist(response_random, skip_checks=False)

        pl = SpotifyPlaylist(response_random, skip_checks=True)
        assert not pl.writeable  # non-user playlists are never writeable

        # no API set, these will not run
        with pytest.raises(APIError):
            await pl.reload()
        with pytest.raises(APIError):
            await pl.delete()
        with pytest.raises(RemoteError):
            await pl.sync()

    def test_writeable(self, response_valid: dict[str, Any], api: SpotifyAPI, api_mock: SpotifyMock):
        pl = SpotifyPlaylist(response_valid)
        assert pl.owner_id == api_mock.user_id  # ensure this is the currently authorised user's playlist
        assert not pl.writeable  # no API set so not writeable

        pl.api = api
        assert pl.writeable  # currently authorised user's playlists are writeable if scope allows it

    def test_attributes(self, response_random: dict[str, Any]):
        pl = SpotifyPlaylist(response_random)
        original_response = deepcopy(response_random)

        assert_id_attributes(item=pl, response=original_response)

        assert len(pl.tracks) == len(pl.response["tracks"]["items"]) == len(pl._tracks)
        assert pl.track_total == pl.response["tracks"]["total"]

        assert pl.name == original_response["name"]
        new_name = "new name"
        pl.name = new_name
        assert pl.response["name"] == new_name

        assert pl.description == original_response["description"]
        new_description = "new description"
        pl.description = new_description
        assert pl.response["description"] == new_description

        assert pl.public is original_response["public"]
        pl.public = not original_response["public"]
        assert pl.response["public"] is not original_response["public"]

        pl.public = False
        pl.collaborative = True
        assert pl.response["collaborative"]
        pl.public = True
        assert not pl.collaborative
        with pytest.raises(SpotifyCollectionError):
            pl.collaborative = True
        pl.public = False
        pl.collaborative = True
        assert pl.collaborative

        assert pl.followers == original_response["followers"]["total"]
        new_followers = pl.followers + 20
        pl.response["followers"]["total"] = new_followers
        assert pl.followers == new_followers

        assert pl.owner_name == original_response["owner"]["display_name"]
        new_owner_name = "new owner name"
        pl.response["owner"]["display_name"] = new_owner_name
        assert pl.owner_name == new_owner_name

        assert pl.owner_id == original_response["owner"]["id"]
        new_owner_id = "new owner id"
        pl.response["owner"]["id"] = new_owner_id
        assert pl.owner_id == new_owner_id

        if not pl.has_image:
            pl.response["images"] = [{"height": 200, "url": "old url"}]
        images = {image["height"]: image["url"] for image in pl.response["images"]}
        assert len(pl.image_links) == 1
        assert pl.image_links["cover_front"] == next(url for height, url in images.items() if height == max(images))
        new_image_link = "new url"
        pl.response["images"].append({"height": max(images) * 2, "url": new_image_link})
        assert pl.image_links["cover_front"] == new_image_link

        original_uris = [track["track"]["uri"] for track in original_response["tracks"]["items"]]
        assert original_uris == pl._get_track_uris_from_api_response()

        assert len(pl.date_added) == len(set(original_uris))
        assert pl.date_created == min(pl.date_added.values())
        assert pl.date_modified == max(pl.date_added.values())
        new_min_dt = datetime.strptime("2000-01-01T00:00:00Z", "%Y-%m-%dT%H:%M:%SZ")
        new_max_dt = datetime.now().replace(tzinfo=None).replace(microsecond=0)
        pl.response["tracks"]["items"].extend([
            {"added_at": new_min_dt.strftime("%Y-%m-%dT%H:%M:%SZ"), "track": {"uri": random_uri()}},
            {"added_at": new_max_dt.strftime("%Y-%m-%dT%H:%M:%SZ"), "track": {"uri": random_uri()}},
        ])
        assert len(pl.date_added) == len(set(original_uris)) + 2
        assert pl.date_created == new_min_dt
        assert pl.date_modified == new_max_dt

    def test_refresh(self, response_valid: dict[str, Any]):
        pl = SpotifyPlaylist(response_valid, skip_checks=True)
        original_track_count = len(pl.tracks)
        pl.response["tracks"]["items"] = pl.response["tracks"]["items"][:original_track_count // 2]

        pl.refresh(skip_checks=True)
        assert len(pl.tracks) == original_track_count // 2

    async def test_reload(self, response_valid: dict[str, Any], api: SpotifyAPI):
        response_valid["description"] = None
        response_valid["public"] = not response_valid["public"]
        response_valid["collaborative"] = not response_valid["collaborative"]

        pl = SpotifyPlaylist(response_valid)
        assert pl.description is None
        assert pl.public is response_valid["public"]
        assert pl.collaborative is response_valid["collaborative"]

        pl.api = api
        await pl.reload(extend_artists=True)
        assert pl.description
        assert pl.public is not response_valid["public"]
        assert pl.collaborative is not response_valid["collaborative"]

    ###########################################################################
    ## Load method tests
    ###########################################################################
    @staticmethod
    async def get_load_without_items(
            loader: SpotifyPlaylist,
            response_valid: dict[str, Any],
            api: SpotifyAPI,
            api_mock: SpotifyMock
    ):
        return await loader.load(response_valid["href"], api=api, extend_tracks=True)

    @pytest.fixture
    def load_items(
            self, response_valid: dict[str, Any], item_key: str, api: SpotifyAPI, api_mock: SpotifyMock
    ) -> list[SpotifyTrack]:
        """
        Extract some item responses from the given ``response_valid`` and remove them from the response.
        This fixture manipulates the ``response_valid`` by removing these items
        and reformatting the values in the items block to ensure 'extend_items' calls can still be run successfully.

        :return: The extracted response as SpotifyTracks.
        """
        key_sub = item_key.rstrip("s")

        # ensure extension of items can be made by reducing available items
        limit = response_valid[item_key]["limit"]
        response_valid[item_key]["items"] = response_valid[item_key][api.items_key][:limit]
        response_items = response_valid[item_key]["items"]
        assert len(response_items) < response_valid[item_key]["total"]

        # produce a list of items for input
        available_ids = {item[key_sub]["id"] for item in response_items}
        limit = len(available_ids) // 2
        items = [SpotifyTrack(response[key_sub]) for response in deepcopy(response_items[:limit])]
        for item in response_items:
            item[key_sub].pop("popularity")

        # ensure all initially available items are covered by the response items and input items
        assert {item[key_sub]["id"] for item in response_items} | {item.id for item in items} == available_ids

        # fix the items block to ensure extension doesn't over/under extend
        response_valid[item_key] = api_mock.format_items_block(
            url=response_valid[item_key]["href"],
            items=response_valid[item_key][api.items_key],
            limit=len(response_valid[item_key][api.items_key]),
            total=response_valid[item_key]["total"],
        )

        return items

    async def test_load_with_all_items(
            self, response_valid: dict[str, Any], item_key: str, api: SpotifyAPI, api_mock: SpotifyMock
    ):
        load_items = [SpotifyTrack(response) for response in response_valid[item_key][api.items_key]]
        await SpotifyPlaylist.load(
            response_valid, api=api, items=load_items, extend_albums=True, extend_tracks=False, extend_features=False
        )

        api_mock.assert_not_called()

    async def test_load_with_some_items(
            self,
            response_valid: dict[str, Any],
            item_key: str,
            load_items: list[SpotifyTrack],
            api: SpotifyAPI,
            api_mock: SpotifyMock
    ):
        kind = RemoteObjectType.PLAYLIST

        result: SpotifyPlaylist = await SpotifyPlaylist.load(
            response_valid, api=api, items=load_items, extend_tracks=True, extend_features=True
        )

        await self.assert_load_with_items_requests(
            response=response_valid, result=result, items=load_items, key=item_key, api_mock=api_mock
        )
        await self.assert_load_with_items_extended(
            response=response_valid, result=result, items=load_items, kind=kind, key=item_key, api_mock=api_mock
        )

        # requests for extension data
        expected = api_mock.calculate_pages_from_response(response_valid)
        # -1 for not calling initial page
        assert len(await api_mock.get_requests(url=f"{result.url}/{item_key}")) == expected - 1
        assert len(await api_mock.get_requests(url=f"{api.url}/audio-features")) == expected

    async def test_load_with_some_items_and_no_extension(
            self,
            response_valid: dict[str, Any],
            item_kind: RemoteObjectType,
            item_key: str,
            load_items: list[SpotifyTrack],
            api: SpotifyAPI,
            api_mock: SpotifyMock
    ):
        await api.extend_items(response_valid, kind=RemoteObjectType.PLAYLIST, key=item_kind)
        api_mock.reset()  # reset for new requests checks to work correctly

        assert len(response_valid[item_key][api.items_key]) == response_valid[item_key]["total"]
        assert not await api_mock.get_requests(url=response_valid[item_key]["href"])

        result: SpotifyPlaylist = await SpotifyPlaylist.load(
            response_valid, api=api, items=load_items, extend_tracks=True, extend_features=False
        )

        await self.assert_load_with_items_requests(
            response=response_valid, result=result, items=load_items, key=item_key, api_mock=api_mock
        )
        assert not await api_mock.get_requests(url=response_valid[item_key]["href"])

        # requests for extension data
        assert not await api_mock.get_requests(url=f"{result.url}/{item_key}")  # already extended on input
        assert not await api_mock.get_requests(url=f"{api.url}/audio-features")

    async def test_create_playlist(self, api: SpotifyAPI, api_mock: SpotifyMock):
        name = "new playlist"
        pl = await SpotifyPlaylist.create(api=api, name="new playlist", public=False, collaborative=True)

        url = f"{api.url}/users/{api_mock.user_id}/playlists"
        _, request, _ = next(iter(await api_mock.get_requests(url=url, response={"name": name})))
        payload = self._get_payload_from_request(request)

        assert payload["name"] == name
        assert PROGRAM_NAME in payload["description"]
        assert not payload["public"]
        assert payload["collaborative"]

        assert pl.name == name
        assert PROGRAM_NAME in pl.description
        assert not pl.public
        assert pl.collaborative

        # should be set in api.create_playlist method
        assert pl.owner_id == api.user_id == api_mock.user_id
        assert pl.writeable

    async def test_delete_playlist(self, response_valid: dict[str, Any], api: SpotifyAPI, api_mock: SpotifyMock):
        names = [pl["name"] for pl in api_mock.user_playlists]
        response = next(deepcopy(pl) for pl in api_mock.user_playlists if names.count(pl["name"]) == 1)
        await api.extend_items(response=response, key=RemoteObjectType.TRACK)
        pl = SpotifyPlaylist(response=response, api=api)
        url = str(pl.url)

        await pl.delete()
        assert await api_mock.get_requests(url=url + "/followers")
        assert not pl.response

    ###########################################################################
    ## Sync tests set up
    ###########################################################################
    @pytest.fixture
    def sync_playlist(self, response_valid: dict[str, Any], api: SpotifyAPI) -> SpotifyPlaylist:
        return SpotifyPlaylist(response=response_valid, api=api)

    @staticmethod
    @pytest.fixture
    def sync_items(
            response_valid: dict[str, Any], response_random: dict[str, Any], api: SpotifyAPI, api_mock: SpotifyMock,
    ) -> list[SpotifyTrack]:
        api_mock.reset()  # reset for new requests checks to work correctly

        uri_valid = [track["track"]["uri"] for track in response_valid["tracks"]["items"]]
        return [
            SpotifyTrack(track["track"]) for track in response_random["tracks"]["items"]
            if track["track"]["uri"] not in uri_valid
        ]

    @classmethod
    async def get_sync_uris(cls, url: str, api_mock: SpotifyMock) -> tuple[list[str], list[str]]:
        requests = await api_mock.get_requests(url=f"{url}/tracks")

        uri_add = []
        uri_clear = []
        for _, request, _ in requests:
            payload = cls._get_payload_from_request(request)
            if not payload:
                continue

            if "uris" in payload:
                uri_add += payload["uris"]
            else:
                uri_clear += [t["uri"] for t in payload["tracks"]]

        return uri_add, uri_clear
