from pathlib import Path

import pytest

from musify.file.path_mapper import PathStemMapper
from musify.libraries.local.track import LocalTrack, FLAC, MP3, M4A, WMA
from musify.libraries.remote.core.wrangle import RemoteDataWrangler
from musify.libraries.remote.spotify.wrangle import SpotifyDataWrangler
from tests.libraries.local.utils import path_track_all, path_track_flac, path_track_mp3, path_track_m4a, path_track_wma
from tests.utils import path_resources


@pytest.fixture(scope="package")
def remote_wrangler(spotify_wrangler: SpotifyDataWrangler) -> RemoteDataWrangler:
    """Yields a :py:class:`SpotifyDataWrangler` to use in tests"""
    yield spotify_wrangler


@pytest.fixture(scope="package")
def path_mapper() -> PathStemMapper:
    """Yields a :py:class:`PathMapper` that can map paths from the test playlist files"""
    yield PathStemMapper(stem_map={"../": path_resources}, available_paths=path_track_all)


@pytest.fixture(params=[path_track_flac])
async def track_flac(path: Path, remote_wrangler: RemoteDataWrangler) -> FLAC:
    """Yields instantiated :py:class:`FLAC` objects for testing"""
    return await FLAC(file=path, remote_wrangler=remote_wrangler)


@pytest.fixture(params=[path_track_mp3])
async def track_mp3(path: Path, remote_wrangler: RemoteDataWrangler) -> MP3:
    """Yields instantiated :py:class:`MP3` objects for testing"""
    return await MP3(file=path, remote_wrangler=remote_wrangler)


@pytest.fixture(params=[path_track_m4a])
async def track_m4a(path: Path, remote_wrangler: RemoteDataWrangler) -> M4A:
    """Yields instantiated :py:class:`M4A` objects for testing"""
    return await M4A(file=path, remote_wrangler=remote_wrangler)


@pytest.fixture(params=[path_track_wma])
async def track_wma(path: Path, remote_wrangler: RemoteDataWrangler) -> WMA:
    """Yields instantiated :py:class:`WMA` objects for testing"""
    return await WMA(file=path, remote_wrangler=remote_wrangler)


# noinspection PyUnresolvedReferences
@pytest.fixture(params=[
    pytest.lazy_fixture("track_flac"),
    pytest.lazy_fixture("track_mp3"),
    pytest.lazy_fixture("track_m4a"),
    pytest.lazy_fixture("track_wma")
])
def track(request) -> LocalTrack:
    """Yields instantiated :py:class:`LocalTrack` objects for testing"""
    return request.param
