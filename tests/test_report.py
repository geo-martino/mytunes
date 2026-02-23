from copy import copy
from pathlib import Path
from random import choice, randrange

import pytest

from musify.libraries.local.library import LocalLibrary
from musify.libraries.local.playlist import M3U
from musify.libraries.local.track.field import LocalTrackField
from musify.libraries.remote.spotify.api import SpotifyAPI
from musify.libraries.remote.spotify.library import SpotifyLibrary
from musify.libraries.remote.spotify.object import SpotifyPlaylist
from musify.libraries.remote.spotify.wrangle import SpotifyDataWrangler
from musify.report import report_playlist_differences, report_missing_tags
from tests.libraries.local.track.utils import random_track
from tests.libraries.remote.spotify.api.mock import SpotifyMock
from tests.libraries.remote.spotify.utils import random_uri


@pytest.fixture
def spotify_library(spotify_api: SpotifyAPI, spotify_mock: SpotifyMock) -> SpotifyLibrary:
    """Yields a :py:class:`SpotifyLibrary` of remote tracks and playlists"""
    library = SpotifyLibrary(api=spotify_api)

    responses = spotify_mock.playlists[:20]
    library._playlists = {
        pl.name: pl
        for pl in map(lambda r: SpotifyPlaylist(api=spotify_api, response=r, skip_checks=True), responses)
        if len(pl) > 30
    }
    for pl in library.playlists.values():  # ensure only unique tracks in each playlist
        pl._tracks = set(pl.tracks)

    library._tracks = [track for pl in library.playlists.values() for track in pl]
    return library


@pytest.fixture
async def local_library(
        spotify_library: SpotifyLibrary, spotify_wrangler: SpotifyDataWrangler, tmp_path: Path
) -> LocalLibrary:
    """Yields a :py:class:`LocalLibrary` of local tracks and playlists"""
    library = LocalLibrary(remote_wrangler=spotify_wrangler)
    library._tracks = [random_track() | track for track in spotify_library.tracks]

    uri_tracks = {track.uri: track for track in library.tracks}
    for name, pl in spotify_library.playlists.items():
        path = tmp_path.joinpath(name).with_suffix(".m3u")
        tracks = [uri_tracks[track.uri] for track in pl]

        playlist = M3U(path=path)
        await playlist.load(tracks=tracks)
        library.playlists[name] = playlist

        assert all(track in pl for track in library.playlists[name])

    return library


def test_report_playlist_differences(local_library: LocalLibrary, spotify_library: SpotifyLibrary):
    # all LocalPlaylists are derived from SpotifyPlaylists, should be no differences
    report = report_playlist_differences(source=local_library, reference=spotify_library)
    assert sum(len(items) for pl in report.values() for items in pl.values()) == 0

    extra_total = 0
    missing_total = 0
    unavailable_total = 0

    playlists = list(local_library.playlists.values())
    for pl_source in playlists:
        # ensure source and reference playlists currently match and all items have URIs
        pl_reference = spotify_library.playlists[pl_source.name]
        assert pl_source == pl_reference
        assert all(track.has_uri for track in pl_source)
        assert all(track.has_uri for track in pl_reference)

        extra = randrange(0, len(pl_source) // 3)
        missing = randrange(0, len(pl_source) // 3)
        unavailable = randrange(0, len(pl_source) // 3)

        extra_total += extra
        missing_total += missing
        unavailable_total += unavailable

        pl_source.tracks = [copy(track) for track in pl_source[extra:]]

        for track in pl_source[:unavailable]:
            track.uri = local_library.remote_wrangler.unavailable_uri_dummy

        added = 0
        while added < missing:
            track = random_track()
            track.uri = random_uri()
            if track not in spotify_library.playlists[pl_source.name]:
                pl_source.append(track)
                added += 1

    report = report_playlist_differences(source=local_library, reference=spotify_library)
    assert sum(map(len, report["Source ✗ | Compare ✓"].values())) == extra_total
    assert sum(map(len, report["Source ✓ | Compare ✗"].values())) == missing_total
    assert sum(map(len, report["Items unavailable (no URI)"].values())) == unavailable_total


@pytest.mark.slow
def test_report_missing_tags(local_library: LocalLibrary):
    albums = {album.name: album for album in local_library.albums}

    # all LocalTracks are derived from SpotifyTracks, none have all tags missing
    assert not report_missing_tags(local_library, match_all=True)

    for track in local_library:  # set up random missing tags
        if choice([True, False]):
            track.genres = []
        if choice([True, False]):
            track.bpm = None
        if choice([True, False]):
            track.key = None
        if choice([True, False]):
            track.disc_total = None

    report = report_missing_tags(local_library)
    assert len(report) == len(albums)
    for name, album in report.items():
        assert len(album) == len(albums[name])

    missing = {tag for items in report.values() for tags in items.values() for tag in tags}
    expected = {"genres", "bpm", "key", "disc_total"}
    assert missing.intersection(expected) == expected

    # limits tag search to those given
    report = report_missing_tags(local_library, tags={LocalTrackField.GENRES, LocalTrackField.KEY})
    assert len(report) == len(albums)
    for name, album in report.items():
        assert len(album) == len(albums[name])

    missing = {tag for items in report.values() for tags in items.values() for tag in tags}
    assert missing == {"genres", "key"}
