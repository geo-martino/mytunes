from random import sample
from typing import Any
from urllib.parse import unquote

from yarl import URL

from musify.models.item.album import Album
from musify.models.item.artist import Artist
from musify.models.item.track import Track
from musify.processors.download.stores import AudioStore
from tests.utils import GENRES


def assert_value_in_url(url: URL, value: Any):
    value = str(value)
    query_values = [unquote(value) for value in url.query.values()]
    assert any(value in v for v in query_values) or value in unquote(url.path)


def assert_value_not_in_url(url: URL, value: Any):
    value = str(value)
    query_values = [unquote(value) for value in url.query.values()]
    assert all(value not in v for v in query_values) and value not in unquote(url.path)


def assert_track_in_url(model: AudioStore, track: Track):
    url = model.format_search_url(track, fields=["name", "artist"])
    assert_value_in_url(url, track.name)
    assert_value_in_url(url, track.artist)


def assert_artist_in_url(model: AudioStore, artist: Artist):
    artist.genres = sample(GENRES, k=3)

    url = model.format_search_url(artist, fields=["name", "genre"])
    assert_value_in_url(url, artist.name)
    assert_value_in_url(url, artist.genres[0].name)


def assert_album_in_url(model: AudioStore, album: Album):
    album.released_at = "2025-01-01"
    url = model.format_search_url(album, fields=["name", "released_at.year"])
    assert_value_in_url(url, album.name)
    assert_value_in_url(url, album.released_at.year)
