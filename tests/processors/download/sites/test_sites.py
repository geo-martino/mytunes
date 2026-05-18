from mytunes.core._item.album import Album
from mytunes.core._item.artist import Artist
from mytunes.core._item.track import Track
from mytunes.processors.download.stores.bandcamp import BandcampStore
from mytunes.processors.download.stores.juno_download import JunoDownloadStore
from mytunes.processors.download.stores.qobuz import QobuzStore
from mytunes.processors.download.stores.seven_digital import SevenDigitalStore
from tests.processors.download.utils import assert_track_in_url, assert_artist_in_url, \
    assert_album_in_url


# Just run a quick check on each store to ensure they render a valid url for tracks

def test_bandcamp(track: Track, artist: Artist, album: Album):
    model = BandcampStore()

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
