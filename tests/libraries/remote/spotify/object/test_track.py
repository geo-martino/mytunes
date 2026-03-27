from copy import deepcopy
from datetime import date
from random import randrange
from typing import Any

import pytest
from aiorequestful.types import Number

from musify.libraries.remote.core.exception import APIError, RemoteObjectTypeError
from musify.libraries.remote.spotify.api import SpotifyAPI
from musify.libraries.remote.spotify.object import SpotifyTrack
from tests.libraries.remote.spotify.api.mock import SpotifyMock
from tests.libraries.remote.spotify.utils import assert_id_attributes
from tests.testers import MusifyItemTester


class TestSpotifyTrack(MusifyItemTester):

    @pytest.fixture
    def item(self, response_random: dict[str, Any]) -> SpotifyTrack:
        return SpotifyTrack(response_random)

    @pytest.fixture
    def item_unequal(self, response_valid: dict[str, Any]) -> SpotifyTrack:
        return SpotifyTrack(response_valid)

    @pytest.fixture
    def item_modified(self, response_random: dict[str, Any]) -> SpotifyTrack:
        track = SpotifyTrack(response_random)
        track.response["name"] = "new name"
        track.response["artists"] = [{"name": artist} for artist in ["artist 1", "artist 2"]]
        track.response["track_number"] = 500
        track.response["popularity"] = 200
        return track

    @pytest.fixture
    def response_random(self, api_mock: SpotifyMock) -> dict[str, Any]:
        """Yield a randomly generated response from the Spotify API for a track item type"""
        return api_mock.generate_track()

    @pytest.fixture
    def response_valid(self, api_mock: SpotifyMock) -> dict[str, Any]:
        """
        Yield a valid enriched response with extended artists and albums responses
        from the Spotify API for a track item type.
        """
        return deepcopy(next(track for track in api_mock.tracks))

    async def test_input_validation(self, response_random: dict[str, Any], api_mock: SpotifyMock):
        with pytest.raises(RemoteObjectTypeError):
            SpotifyTrack(api_mock.generate_artist(properties=False))
        with pytest.raises(APIError):
            await SpotifyTrack(response_random).reload()

    def test_attributes(self, response_random: dict[str, Any]):
        track = SpotifyTrack(response_random)
        original_response = deepcopy(response_random)

        assert_id_attributes(item=track, response=original_response)

        assert track.name == track.title
        assert track.title == original_response["name"]
        new_name = "new name"
        track.response["name"] = new_name
        assert track.title == new_name

        original_artists = [artist["name"] for artist in original_response["artists"]]
        assert track.artist == track.tag_sep.join(original_artists)
        assert len(track.artists) == len(original_artists)
        new_artists = ["artist 1", "artist 2"]
        track.response["artists"] = [{"name": artist} for artist in new_artists]
        assert track.artist == track.tag_sep.join(new_artists)

        assert track.album == original_response["album"]["name"]
        new_album = "new album"
        track.response["album"]["name"] = new_album
        assert track.album == new_album

        original_album_artists = [artist["name"] for artist in original_response["album"]["artists"]]
        original_album_artist = track.tag_sep.join(original_album_artists)
        assert track.album_artist == original_album_artist
        new_album_artists = ["album artist 1", "album artist 2"]
        track.response["album"]["artists"] = [{"name": artist} for artist in new_album_artists]
        assert track.album_artist == track.tag_sep.join(new_album_artists)

        assert track.track_number == original_response["track_number"]
        new_track_number = track.track_number + 4
        track.response["track_number"] = new_track_number
        assert track.track_number == new_track_number

        assert track.track_total == original_response["album"]["total_tracks"]
        new_track_total = track.track_total + 20
        track.response["album"]["total_tracks"] = new_track_total
        assert track.track_total == new_track_total

        assert not original_response["album"].get("genres")
        assert not original_response["artists"][0].get("genres")
        assert not track.genres
        new_genres_artist = ["electronic", "dance"]
        track.response["artists"][0]["genres"] = new_genres_artist
        assert track.genres == [g.title() for g in new_genres_artist]
        new_genres_album = ["rock", "jazz", "pop rock"]
        track.response["album"]["genres"] = new_genres_album
        assert track.genres == [g.title() for g in new_genres_album]

        date_split = list(map(int, original_response["album"]["release_date"].split("-")))
        assert track.year == date_split[0]
        if original_response["album"]["release_date_precision"] in {"month", "day"}:
            assert track.month == date_split[1]
        else:
            assert track.month is None
        if original_response["album"]["release_date_precision"] in {"day"}:
            assert track.day == date_split[2]
            assert track.date == date(*date_split)
        else:
            assert track.day is None
            assert track.date is None
        new_year = track.year + 20
        new_month = randrange(1, 12)
        new_day = randrange(1, 28)
        track.response["album"]["release_date"] = f"{new_year}-{new_month}-{new_day}"
        track.response["album"]["release_date_precision"] = "day"
        assert track.date == date(new_year, new_month, new_day)
        assert track.year == new_year
        assert track.month == new_month
        assert track.day == new_day

        assert "audio_features" not in track.response
        assert not track.bpm
        new_bpm = 120.123
        track.response["audio_features"] = {"tempo": 120.123}
        assert track.bpm == new_bpm
        track.response.pop("audio_features")

        assert not track.key
        new_key = 4
        track.response["audio_features"] = {"key": new_key, "mode": 1}
        assert track.key == track._song_keys[new_key]
        track.response["audio_features"]["mode"] = 0
        assert track.key == track._song_keys[new_key] + "m"
        track.response["audio_features"] = {"key": -1, "mode": 0}
        assert not track.key

        assert not track.disc_total
        assert track.disc_number == original_response["disc_number"]
        new_disc_number = track.disc_number + 5
        track.response["disc_number"] = new_disc_number
        assert track.disc_number == new_disc_number

        track.response["album"]["album_type"] = "compilation"
        assert track.compilation
        track.response["album"]["album_type"] = "album"
        assert not track.compilation

        if not track.has_image:
            track.response["album"]["images"] = [{"height": 200, "url": "old url"}]
        images = {image["height"]: image["url"] for image in track.response["album"]["images"]}
        assert len(track.image_links) == 1
        assert track.image_links["cover_front"] == next(url for height, url in images.items() if height == max(images))
        new_image_link = "new url"
        track.response["album"]["images"].append({"height": max(images) * 2, "url": new_image_link})
        assert track.image_links["cover_front"] == new_image_link

        original_duration = int(
            original_response["duration_ms"] if isinstance(original_response["duration_ms"], Number)
            else original_response["duration_ms"]["totalMilliseconds"]
        ) / 1000
        assert track.length == original_duration
        new_duration = original_duration + 2000
        track.response["duration_ms"] = new_duration
        assert track.length == new_duration / 1000

        assert track.rating == original_response["popularity"]
        new_rating = track.rating + 20
        track.response["popularity"] = new_rating
        assert track.rating == new_rating

    def test_refresh(self, response_valid: dict[str, Any]):
        track = SpotifyTrack(response_valid, skip_checks=True)
        track.response["artists"] = [track.response["artists"][0]]

        track.refresh(skip_checks=True)
        assert len(track.artists) == 1

    async def test_reload(self, response_valid: dict[str, Any], api: SpotifyAPI):
        response_valid["album"].pop("name", None)
        response_valid.pop("audio_features", None)

        track = SpotifyTrack(response_valid)
        assert not track.album
        assert not track.key
        assert not track.bpm

        track.api = api
        await track.reload(features=True)
        assert track.album
        if track.response["audio_features"]["key"] > -1:
            assert track.key
        else:
            assert track.key is None
        assert track.bpm

    async def test_load(self, response_valid: dict[str, Any], api: SpotifyAPI):
        track = await SpotifyTrack.load(response_valid["href"], api=api)

        assert track.name == response_valid["name"]
        assert track.id == response_valid["id"]
        assert str(track.url) == response_valid["href"]
