from collections.abc import Collection
from copy import deepcopy
from random import sample, choice, randrange
from typing import Any

import pytest

from musify._types import Resource
from musify.libraries.remote.spotify.api import SpotifyAPI
from musify.libraries.remote.spotify.api.item import ARTIST_ALBUM_TYPES
from musify.libraries.remote.spotify.object import SpotifyArtist
from tests.libraries.remote.spotify.api.mock import SpotifyMock
from tests.libraries.remote.spotify.api.utils import assert_calls, get_limit
from tests.libraries.remote.spotify.utils import random_id_type, random_id_types


class TestSpotifyAPIArtists:
    """Tester for a subsection of artist-type endpoints of :py:class:`SpotifyAPI`"""

    @pytest.fixture
    def artist_album_types(self) -> tuple[str, ...]:
        """Yields the artist album types to get for a given artist as a pytest.fixture."""
        return tuple(sample(sorted(ARTIST_ALBUM_TYPES), k=randrange(2, len(ARTIST_ALBUM_TYPES))))

    # noinspection PyTestUnpassedFixture
    @pytest.fixture
    def artists_albums(
            self, artist_album_types: tuple[str, ...], api_mock: SpotifyMock
    ) -> dict[str, list[dict[str, Any]]]:
        """
        Yields a complete map of artist ID to the artist's albums
        for a given set of ``artist_album_types`` as a pytest.fixture
        """
        def get_artist_albums(artist_id: str) -> list[dict[str, Any]]:
            """Get the albums associated with a given ``artist_id``"""
            return [
                album for album in api_mock.artist_albums
                if any(artist["id"] == artist_id for artist in album["artists"])
                and album["album_type"] in artist_album_types
            ]

        artists_albums = {artist["id"]: get_artist_albums(artist["id"]) for artist in api_mock.artists}
        return {artist_id: deepcopy(albums) for artist_id, albums in artists_albums.items() if albums}

    @pytest.fixture
    def artist_albums(
            self, artist: dict[str, Any], artists_albums: dict[str, list[dict[str, Any]]]
    ) -> list[dict[str, Any]]:
        """Yields the albums for a given ``artist`` as a pytest.fixture."""
        return deepcopy(artists_albums[artist["id"]])

    # noinspection PyTestUnpassedFixture
    @pytest.fixture
    def artists(self, artists_albums: Collection[str], api_mock: SpotifyMock) -> dict[str, dict[str, Any]]:
        """
        Yields a complete map of artist ID to artist for a set of IDs
        as given by ``artists_albums`` as a pytest.fixture.
        """
        return {artist["id"]: deepcopy(artist) for artist in api_mock.artists if artist["id"] in artists_albums}

    @pytest.fixture
    def artist(self, artists: dict[Any, dict[str, Any]]) -> dict[str, Any]:
        """Yields a randomly selected artist from a given set of ``artists`` as a pytest.fixture."""
        return choice(list(artists.values()))

    @staticmethod
    def assert_artist_albums_enriched(albums: list[dict[str, Any]]) -> None:
        """Check that all albums have been enriched with a skeleton items block"""
        for album in albums:
            assert "tracks" in album
            assert album["tracks"]["total"] == album["total_tracks"]
            assert album["id"] in album["tracks"]["href"]

    async def assert_artist_albums_results(
            self,
            results: dict[str, list[dict[str, Any]]],
            source: dict[str, dict[str, Any]],
            expected: dict[str, list[dict[str, Any]]],
            api: SpotifyAPI,
            api_mock: SpotifyMock,
            limit: int,
            update: bool,
    ):
        """Assert the results of the get_artist_albums operation"""
        assert len(results) == len(expected)

        for id_, result in results.items():
            assert [{k: v for k, v in r.items() if k != "tracks"} for r in result] == expected[id_]
            self.assert_artist_albums_enriched(result)

            # appropriate number of requests made
            url = f"{api.url}/artists/{id_}/albums"
            requests = await api_mock.get_requests(url=url)
            assert_calls(expected=expected[id_], requests=requests, limit=limit, api_mock=api_mock)

            if not update:
                assert "albums" not in source[id_]
                return

            assert len(source[id_]["albums"]["items"]) == source[id_]["albums"]["total"] == len(expected[id_])
            reduced = [{k: v for k, v in album.items() if k != "tracks"} for album in source[id_]["albums"]["items"]]
            assert reduced == expected[id_]
            self.assert_artist_albums_enriched(source[id_]["albums"]["items"])

    async def test_get_artist_albums_single_string(
            self,
            artist_albums: list[dict[str, Any]],
            artist: dict[str, Any],
            artist_album_types: tuple[str, ...],
            api: SpotifyAPI,
            api_mock: SpotifyMock,
    ):
        limit = get_limit(artist_albums, api_mock.limit_max)
        results = await api.get_artist_albums(
            values=random_id_type(id_=artist["id"], wrangler=api.wrangler, kind=Resource.ARTIST),
            types=artist_album_types,
            limit=limit
        )

        await self.assert_artist_albums_results(
            results=results,
            source={artist["id"]: artist},
            expected={artist["id"]: artist_albums},
            api=api,
            api_mock=api_mock,
            limit=limit,
            update=False
        )

    async def test_get_artist_albums_single_mapping(
            self,
            artist_albums: list[dict[str, Any]],
            artist: dict[str, Any],
            artist_album_types: tuple[str, ...],
            api: SpotifyAPI,
            api_mock: SpotifyMock,
    ):
        limit = get_limit(artist_albums, api_mock.limit_max)
        results = await api.get_artist_albums(values=artist, types=artist_album_types, limit=limit)

        await self.assert_artist_albums_results(
            results=results,
            source={artist["id"]: artist},
            expected={artist["id"]: artist_albums},
            api=api,
            api_mock=api_mock,
            limit=limit,
            update=True
        )

    async def test_get_artist_albums_many_string(
            self,
            artists_albums: dict[str, list[dict[str, Any]]],
            artists: dict[str, dict[str, Any]],
            artist_album_types: tuple[str, ...],
            api: SpotifyAPI,
            api_mock: SpotifyMock,
    ):
        limit = 50
        results = await api.get_artist_albums(
            values=random_id_types(id_list=artists, wrangler=api.wrangler, kind=Resource.ARTIST),
            types=artist_album_types,
            limit=limit,
        )

        await self.assert_artist_albums_results(
            results=results,
            source=artists,
            expected=artists_albums,
            api=api,
            api_mock=api_mock,
            limit=limit,
            update=False
        )

    async def test_get_artist_albums_many_mapping(
            self,
            artists_albums: dict[str, list[dict[str, Any]]],
            artists: dict[str, dict[str, Any]],
            artist_album_types: tuple[str, ...],
            api: SpotifyAPI,
            api_mock: SpotifyMock,
    ):
        limit = 50
        results = await api.get_artist_albums(values=artists.values(), types=artist_album_types, limit=limit)

        await self.assert_artist_albums_results(
            results=results,
            source=artists,
            expected=artists_albums,
            api=api,
            api_mock=api_mock,
            limit=limit,
            update=True
        )

    async def test_artist_albums_single_response(
            self,
            artist_albums: list[dict[str, Any]],
            artist: dict[str, Any],
            artist_album_types: tuple[str, ...],
            api: SpotifyAPI,
            api_mock: SpotifyMock,
    ):
        test = SpotifyArtist(artist, skip_checks=True)
        assert len(test.albums) < len(artist_albums)

        await api.get_artist_albums(values=test, types=artist_album_types)
        assert len(test.albums) == len(artist_albums)

    async def test_artist_albums_many_response(
            self,
            artists_albums: dict[str, list[dict[str, Any]]],
            artists: dict[str, dict[str, Any]],
            artist_album_types: tuple[str, ...],
            api: SpotifyAPI,
            api_mock: SpotifyMock,
    ):
        test = [SpotifyArtist(artist, skip_checks=True) for artist in artists.values()]
        for artist in test:
            assert len(artist.albums) < len(artists_albums[artist.id])

        await api.get_artist_albums(values=test, types=artist_album_types)
        for artist in test:
            assert len(artist.albums) == len(artists_albums[artist.id])
