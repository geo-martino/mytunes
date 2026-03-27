from copy import deepcopy
from random import sample
from urllib.parse import unquote

import pytest

from musify.libraries.remote.core.types import RemoteObjectType
from musify.libraries.remote.spotify.api import SpotifyAPI
from musify.libraries.remote.spotify.library import SpotifyLibrary
from musify.libraries.remote.spotify.object import SpotifyTrack
from musify.processors.filter import FilterDefinedList, FilterIncludeExclude
from tests.libraries.remote.core.library import RemoteLibraryTester
from tests.libraries.remote.spotify.api.mock import SpotifyMock


class TestSpotifyLibrary(RemoteLibraryTester):

    @pytest.fixture
    def collection_merge_items(self, api_mock: SpotifyMock) -> list[SpotifyTrack]:
        tracks = list(map(SpotifyTrack, deepcopy(api_mock.tracks[api_mock.range_max: api_mock.range_max + 10])))
        assert len(tracks) > 4
        return tracks

    @pytest.fixture
    def library_unloaded(self, api: SpotifyAPI, api_mock: SpotifyMock) -> SpotifyLibrary:
        """Yields an unloaded Library object to be tested as pytest.fixture."""
        include = FilterDefinedList([pl["name"] for pl in sample(api_mock.user_playlists, k=10)])
        return SpotifyLibrary(api=api, playlist_filter=include)

    @pytest.fixture(scope="class")
    async def _library(self, api: SpotifyAPI, _api_mock: SpotifyMock) -> SpotifyLibrary:
        include = FilterDefinedList([pl["name"] for pl in sample(_api_mock.user_playlists, k=10)])
        library = SpotifyLibrary(api=api, playlist_filter=include)
        await library.load()
        return library

    @pytest.fixture
    def library(self, _library: SpotifyLibrary) -> SpotifyLibrary:
        return deepcopy(_library)

    async def test_filter_playlists(self, api: SpotifyAPI, api_mock: SpotifyMock):
        # keep all when no include or exclude settings defined
        library = SpotifyLibrary(api=api)

        responses = await api.get_user_items(kind=RemoteObjectType.PLAYLIST)
        filtered = library._filter_playlists(responses)
        assert len(filtered) == len(api_mock.user_playlists) == len(responses)

        # filter on include and exclude
        library.playlist_filter = FilterIncludeExclude(
            include=FilterDefinedList([pl["name"] for pl in api_mock.user_playlists[:20]]),
            exclude=FilterDefinedList([pl["name"] for pl in api_mock.user_playlists[:10]])
        )
        pl_responses = library._filter_playlists(responses)
        assert len(pl_responses) == 10

    ###########################################################################
    ## Load tests
    ###########################################################################
    async def test_load_tracks(self, library_unloaded: SpotifyLibrary, api_mock: SpotifyMock):
        await library_unloaded.load_tracks()
        assert len(library_unloaded.tracks) == len(api_mock.user_tracks)

        # does not add duplicates to the loaded list
        await library_unloaded.load_tracks()
        assert len(library_unloaded.tracks) == len(api_mock.user_tracks)

    async def test_load_saved_albums(self, library_unloaded: SpotifyLibrary, api_mock: SpotifyMock):
        await library_unloaded.load_saved_albums()
        assert len(library_unloaded.albums) == len(api_mock.user_albums)

        # does not add duplicates to the loaded list
        await library_unloaded.load_saved_albums()
        assert len(library_unloaded.albums) == len(api_mock.user_albums)

    async def test_load_saved_artists(self, library_unloaded: SpotifyLibrary, api_mock: SpotifyMock):
        await library_unloaded.load_saved_artists()
        assert len(library_unloaded.artists) == len(api_mock.user_artists)

        # does not add duplicates to the loaded list
        await library_unloaded.load_saved_artists()
        assert len(library_unloaded.artists) == len(api_mock.user_artists)

    ###########################################################################
    ## Enrich tests
    ###########################################################################
    # noinspection PyTestUnpassedFixture
    @pytest.mark.slow
    async def test_enrich_tracks(self, library: SpotifyLibrary, api_mock: SpotifyMock, **kwargs):
        def validate_track_extras_not_enriched(t: SpotifyTrack) -> None:
            """Check track does not contain audio features or analysis fields"""
            assert "audio_features" not in t.response
            assert "audio_analysis" not in t.response

        def validate_album_not_enriched(t: SpotifyTrack) -> None:
            """Check album does not contain expected enriched fields"""
            assert "external_ids" not in t.response["album"]
            assert "genres" not in t.response["album"]
            assert "popularity" not in t.response["album"]

        def validate_artists_not_enriched(t: SpotifyTrack) -> None:
            """Check artists do not contain expected enriched fields"""
            for art in t.response["artists"]:
                assert "followers" not in art
                assert "images" not in art
                assert "popularity" not in art

        # ensure tracks are not enriched already
        artist_ids = {artist["id"] for track in library.tracks for artist in track.response["artists"]}
        album_ids = {track.response["album"]["id"] for track in library.tracks}
        track_album_map = {track.uri: track.album for track in library.tracks}
        track_artists_map = {track.uri: [a.name for a in track.artists] for track in library.tracks}
        for track in library.tracks:
            validate_track_extras_not_enriched(track)
            validate_album_not_enriched(track)
            validate_artists_not_enriched(track)

        # enriches only albums
        await library.enrich_tracks(albums=True, artists=False)
        for track in library.tracks:
            assert track.album == track_album_map[track.uri]
            assert "external_ids" in track.response["album"]
            assert "genres" in track.response["album"]
            assert "popularity" in track.response["album"]
            assert "tracks" not in track.response["album"]

            validate_track_extras_not_enriched(track)
            validate_artists_not_enriched(track)

            assert len(await api_mock.get_requests(url=track.response["album"]["href"] + "/tracks")) == 0

        # check requests
        assert len(await api_mock.get_requests(url=f"{library.api.url}/artists")) == 0
        req_albums = await api_mock.get_requests(url=f"{library.api.url}/albums")
        req_album_ids = {id_ for url, _, _ in req_albums for id_ in unquote(url.query["ids"]).split(",")}
        assert req_album_ids == album_ids

        api_mock.reset()  # reset for new requests checks to work correctly

        # enriches artists without replacing previous enrichment
        await library.enrich_tracks(albums=False, artists=True)
        for track in library.tracks:
            assert track.album == track_album_map[track.uri]
            assert "external_ids" in track.response["album"]
            assert "genres" in track.response["album"]
            assert "popularity" in track.response["album"]
            assert "tracks" not in track.response["album"]

            assert len(await api_mock.get_requests(url=track.response["album"]["href"] + "/tracks")) == 0

            assert [a.name for a in track.artists] == track_artists_map[track.uri]
            for artist in track.response["artists"]:
                assert "followers" in artist
                assert "images" in artist
                assert "popularity" in artist

            validate_track_extras_not_enriched(track)

        # check requests
        assert len(await api_mock.get_requests(url=f"{library.api.url}/albums")) == 0
        req_artists = await api_mock.get_requests(url=f"{library.api.url}/artists")
        req_artist_ids = {id_ for url, _, _ in req_artists for id_ in unquote(url.query["ids"]).split(",")}
        assert req_artist_ids == artist_ids

        # just check these fields were now added
        await library.enrich_tracks(features=True, analysis=True)
        for track in library.tracks:
            assert "audio_features" in track.response
            assert "audio_analysis" in track.response

    @pytest.mark.slow
    async def test_enrich_saved_albums(self, library: SpotifyLibrary, **kwargs):
        # ensure at least some albums are not enriched already
        assert any(len(album.response["tracks"]["items"]) != album.track_total for album in library.albums)
        assert any(len(album.tracks) != album.track_total for album in library.albums)

        await library.enrich_saved_albums()
        for album in library.albums:
            assert len(album.response["tracks"]["items"]) == album.track_total
            assert len(album.tracks) == album.track_total

    @pytest.mark.slow
    async def test_enrich_saved_artists(self, library: SpotifyLibrary, api_mock: SpotifyMock, **kwargs):
        # ensure artists are not enriched already
        for artist in library.artists:
            assert "albums" not in artist.response
            assert len(artist.albums) == 0

        # gets albums but does not extend them
        await library.enrich_saved_artists(tracks=False)
        assert any(len(artist.response["albums"]["items"]) > 0 for artist in library.artists)
        for artist in library.artists:
            assert "albums" in artist.response
            assert len(artist.response["albums"]["items"]) == len(artist.albums)

            for response in artist.response["albums"]["items"]:
                assert len(response["tracks"].get("items", [])) == 0
            for album in artist.albums:
                assert len(album.tracks) == len(album.response["tracks"].get("items", [])) == 0

        # only album URLs were called
        req_urls = sorted(str(url.with_query(None)) for url, _, _ in await api_mock.get_requests())
        assert req_urls == sorted(str(artist.url) + "/albums" for artist in library.artists)

        await library.enrich_saved_artists(tracks=True)
        for artist in library.artists:
            for response in artist.response["albums"]["items"]:
                assert len(response["tracks"].get("items", [])) == response["total_tracks"] > 0
            for album in artist.albums:
                assert len(album.tracks) == len(album.response["tracks"].get("items", [])) == album.track_total > 0

        req_urls = set(str(url.with_query(None)) for url, _, _ in await api_mock.get_requests())
        assert all(str(album.url) + "/tracks" in req_urls for artist in library.artists for album in artist.albums)
