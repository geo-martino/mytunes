from collections.abc import Iterable
from copy import deepcopy
from random import randrange
from typing import Any

import pytest
from yarl import URL

from musify._types import Resource
from musify.libraries.remote.core.exception import APIError, RemoteObjectTypeError
from musify.libraries.remote.spotify.api import SpotifyAPI
from musify.libraries.remote.spotify.object import SpotifyAlbum, SpotifyArtist
from tests.libraries.remote.spotify.api.mock import SpotifyMock
from tests.libraries.remote.spotify.object.testers import SpotifyCollectionLoaderTester
from tests.libraries.remote.spotify.utils import assert_id_attributes


class TestSpotifyArtist(SpotifyCollectionLoaderTester):

    @pytest.fixture
    def collection(self, response_random: dict[str, Any]) -> SpotifyArtist:
        artist = SpotifyArtist(response_random)
        artist._albums = [item for item in artist.items if artist.items.count(item) == 1]
        return artist

    @pytest.fixture
    def collection_merge_items(self, api_mock: SpotifyMock) -> Iterable[SpotifyAlbum]:
        albums = [api_mock.generate_album() for _ in range(randrange(5, 10))]
        for album in albums:
            album["total_tracks"] = len(album["tracks"]["items"])

        return list(map(SpotifyAlbum, albums))

    @pytest.fixture
    def item_kind(self, *_) -> Resource:
        return Resource.ALBUM

    @pytest.fixture
    def response_random(self, api_mock: SpotifyMock) -> dict[str, Any]:
        """Yield a randomly generated response from the Spotify API for an artist item type"""
        artist = api_mock.generate_artist()
        albums = [
            api_mock.generate_album(tracks=False, artists=False, use_stored=False)
            for _ in range(randrange(5, 10))
        ]
        for album in albums:
            album["artists"] = [deepcopy(artist)]
            album["total_tracks"] = 0

        items_block = api_mock.format_items_block(
            url=f"{api_mock.url_api}/artists/{artist["id"]}/albums", items=albums, total=len(albums)
        )
        return artist | {"albums": items_block}

    @pytest.fixture
    def response_valid(self, api_mock: SpotifyMock) -> dict[str, Any]:
        """Yield a valid enriched response from the Spotify API for an artist item type."""
        artist_album_map = {
            artist["id"]: [
                deepcopy(album) for album in api_mock.artist_albums
                if any(art["id"] == artist["id"] for art in album["artists"])
            ]
            for artist in api_mock.artists
        }
        id_, albums = next((id_, albums) for id_, albums in artist_album_map.items() if len(albums) >= 10)
        artist = next(deepcopy(artist) for artist in api_mock.artists if artist["id"] == id_)

        for album in albums:
            tracks = [deepcopy(track) for track in api_mock.tracks if track["album"]["id"] == album["id"]]
            [track.pop("popularity", None) for track in tracks]
            tracks = [track | {"track_number": i} for i, track in enumerate(tracks, 1)]

            album["tracks"] = api_mock.format_items_block(url=album["href"], items=tracks, total=len(tracks))

        items_block = api_mock.format_items_block(
            url=f"{api_mock.url_api}/artists/{artist["id"]}/albums", items=albums, total=len(albums)
        )
        return artist | {"albums": items_block}

    async def test_input_validation(self, response_random: dict[str, Any], api_mock: SpotifyMock):
        with pytest.raises(RemoteObjectTypeError):
            SpotifyArtist(api_mock.generate_track(artists=False, album=False))
        with pytest.raises(APIError):
            await SpotifyArtist(response_random).reload()

    def test_attributes(self, response_random: dict[str, Any]):
        artist = SpotifyArtist(response_random)
        original_response = deepcopy(response_random)

        assert_id_attributes(item=artist, response=original_response)
        assert len(artist.albums) == len(original_response["albums"]["items"])
        assert len(artist.artists) == len({art.name for album in artist.albums for art in album.artists})
        assert len(artist.tracks) == artist.track_total == sum(map(len, artist.albums))

        assert artist.name == artist.artist
        assert artist.artist == original_response["name"]
        new_name = "new name"
        artist.response["name"] = new_name
        assert artist.artist == new_name

        assert artist.genres == original_response["genres"]
        new_genres = ["electronic", "dance"]
        artist.response["genres"] = new_genres
        assert artist.genres == new_genres

        if not artist.has_image:
            artist.response["images"] = [{"height": 200, "url": "old url"}]
        images = {image["height"]: image["url"] for image in artist.response["images"]}
        assert len(artist.image_links) == 1
        assert artist.image_links["cover_front"] == next(url for height, url in images.items() if height == max(images))
        new_image_link = "new url"
        artist.response["images"].append({"height": max(images) * 2, "url": new_image_link})
        assert artist.image_links["cover_front"] == new_image_link

        assert artist.rating == original_response["popularity"]
        new_rating = artist.rating + 20
        artist.response["popularity"] = new_rating
        assert artist.rating == new_rating

        assert artist.followers == original_response["followers"]["total"]
        new_followers = artist.followers + 20
        artist.response["followers"]["total"] = new_followers
        assert artist.followers == new_followers

    def test_refresh(self, response_valid: dict[str, Any]):
        artist = SpotifyArtist(response_valid, skip_checks=True)
        original_album_count = len(artist.albums)
        artist.response["albums"]["items"] = artist.response["albums"]["items"][:original_album_count // 2]

        artist.refresh(skip_checks=True)
        assert len(artist.albums) == original_album_count // 2

    async def test_reload(self, response_valid: dict[str, Any], api: SpotifyAPI):
        genres = response_valid.pop("genres", None)
        response_valid.pop("popularity", None)
        response_valid.pop("followers", None)

        albums = response_valid.pop("albums")["items"]
        album_ids = {album["id"] for album in albums}
        artist_names = {artist["name"] for album in albums for artist in album["artists"]}

        artist = SpotifyArtist(response_valid)
        assert not artist.genres
        assert artist.rating is None
        assert artist.followers is None
        assert not artist.albums
        assert not artist.artists
        assert not artist.tracks

        artist.api = api
        await artist.reload(extend_albums=False, extend_tracks=True)
        if genres:
            assert artist.genres
        assert artist.rating is not None
        assert artist.followers is not None
        assert not artist.albums
        assert not artist.artists
        assert not artist.tracks

        await artist.reload(extend_albums=True, extend_tracks=False)
        assert {album.id for album in artist._albums} == album_ids
        assert len(artist.artists) == len(artist_names)
        assert set(artist.artists) == artist_names
        assert not artist.tracks

        await artist.reload(extend_albums=True, extend_tracks=True)
        assert artist.tracks

    ###########################################################################
    ## Load method tests
    ###########################################################################
    @staticmethod
    async def get_load_without_items(
            loader: SpotifyArtist,
            response_valid: dict[str, Any],
            api: SpotifyAPI,
            api_mock: SpotifyMock
    ):
        return await loader.load(response_valid["href"], api=api, extend_albums=True, extend_tracks=True)

    @pytest.fixture
    def load_items(
            self, response_valid: dict[str, Any], item_key: str, api: SpotifyAPI, api_mock: SpotifyMock
    ) -> list[SpotifyAlbum]:
        """
        Extract some item responses from the given ``response_valid`` and remove them from the response.
        This fixture manipulates the ``response_valid`` by removing these items
        and reformatting the values in the items block to ensure 'extend_items' calls can still be run successfully.

        :return: The extracted response as SpotifyTracks.
        """

        # ensure extension of items can be made by reducing available items
        limit = response_valid[item_key]["limit"]
        response_valid[item_key]["items"] = response_valid[item_key][api.items_key][:limit]
        response_items = response_valid[item_key]["items"]
        assert len(response_items) < response_valid[item_key]["total"]

        # produce a list of items for input
        available_ids = {item["id"] for item in response_items}
        limit = len(available_ids) // 2
        items = [SpotifyAlbum(response, skip_checks=True) for response in deepcopy(response_items[:limit])]

        # ensure all initially available items are covered by the response items and input items
        assert {item["id"] for item in response_items} | {item.id for item in items} == available_ids

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
        load_items = [SpotifyAlbum(response, skip_checks=True) for response in response_valid[item_key][api.items_key]]
        await SpotifyArtist.load(
            response_valid, api=api, items=load_items, extend_albums=True, extend_tracks=False, extend_features=False
        )

        api_mock.assert_not_called()

    async def test_load_with_some_items(
            self,
            response_valid: dict[str, Any],
            item_key: str,
            load_items: list[SpotifyAlbum],
            api: SpotifyAPI,
            api_mock: SpotifyMock
    ):
        kind = Resource.ARTIST

        result: SpotifyArtist = await SpotifyArtist.load(
            response_valid, api=api, items=load_items, extend_albums=True, extend_tracks=True, extend_features=True
        )

        await self.assert_load_with_items_requests(
            response=response_valid, result=result, items=load_items, key=item_key, api_mock=api_mock
        )
        await self.assert_load_with_items_extended(
            response=response_valid, result=result, items=load_items, kind=kind, key=item_key, api_mock=api_mock
        )

        # requests for extension data
        expected = api_mock.calculate_pages_from_response(response_valid, item_key=item_key)
        assert len(await api_mock.get_requests(url=f"{result.url}/{item_key}")) == expected

        for album in result.response[item_key][api.items_key]:
            url = URL(album["tracks"]["href"]).with_query(None)
            expected = api_mock.calculate_pages_from_response(album)
            assert len(await api_mock.get_requests(url=url)) == expected

        assert result.tracks
        expected_features = api_mock.calculate_pages(limit=response_valid[item_key]["limit"], total=len(result.tracks))
        assert len(await api_mock.get_requests(url=f"{api.url}/audio-features")) == expected_features

    async def test_load_with_some_items_and_no_extension(
            self,
            response_valid: dict[str, Any],
            item_kind: Resource,
            item_key: str,
            load_items: list[SpotifyAlbum],
            api: SpotifyAPI,
            api_mock: SpotifyMock
    ):
        await api.extend_items(response_valid, kind=Resource.ARTIST, key=item_kind)
        api_mock.reset()  # reset for new requests checks to work correctly

        assert len(response_valid[item_key][api.items_key]) == response_valid[item_key]["total"]
        assert not await api_mock.get_requests(url=response_valid[item_key]["href"])

        result: SpotifyArtist = await SpotifyArtist.load(response_valid, api=api, items=load_items, extend_albums=True)

        await self.assert_load_with_items_requests(
            response=response_valid, result=result, items=load_items, key=item_key, api_mock=api_mock
        )

        # requests for extension data
        assert not await api_mock.get_requests(url=f"{result.url}/{item_key}")
        assert not await api_mock.get_requests(url=f"{api.url}/audio-features")
        assert not await api_mock.get_requests(url=f"{api.url}/artists")
