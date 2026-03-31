from musify.models.item.album import Album
from musify.models.item.artist import Artist
from musify.models.item.track import Track
from musify.processors.download.sites.bandcamp import BandcampStore
from musify.processors.download.sites.jackett import JackettStore
from musify.processors.download.sites.juno_download import JunoDownloadStore
from musify.processors.download.sites.qobuz import QobuzStore
from musify.processors.download.sites.seven_digital import SevenDigitalStore
from tests.processors.download.utils import assert_value_in_url, assert_track_in_url, assert_artist_in_url, \
    assert_album_in_url


# Just run a quick check on each store to ensure they render a valid url for tracks



def test_bandcamp(track: Track, artist: Artist, album: Album):
    model = BandcampStore()

    assert_track_in_url(model, track)
    assert_artist_in_url(model, artist)
    assert_album_in_url(model, album)


def test_jackett(track: Track, artist: Artist, album: Album):
    model = JackettStore(url="https://jackett.com")

    assert_track_in_url(model, track)
    assert_artist_in_url(model, artist)
    assert_album_in_url(model, album)


def test_juno_download(track: Track, artist: Artist, album: Album):
    model = JunoDownloadStore()

    assert_track_in_url(model, track)
    assert_album_in_url(model, album)


def test_qobuz(track: Track, artist: Artist, album: Album):
    model = QobuzStore()

    assert_track_in_url(model, track)
    assert_artist_in_url(model, artist)
    assert_album_in_url(model, album)


def test_7digital(track: Track, artist: Artist, album: Album):
    model = SevenDigitalStore(locale="en_gb")

    assert_track_in_url(model, track)
    assert_artist_in_url(model, artist)
    assert_album_in_url(model, album)
