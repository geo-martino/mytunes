from copy import copy, deepcopy
from datetime import datetime, date
from pathlib import Path
from random import choice

import mutagen
import pytest

from musify.base import MusifyItem
from musify.exception import MusifyKeyError
from musify.file.exception import InvalidFileType, FileDoesNotExistError
from musify.file.image import open_image
from musify.libraries.core.object import Track
from musify.libraries.local.track import LocalTrack, load_track, FLAC, M4A, MP3, WMA, SyncResultTrack
from musify.libraries.local.track.field import LocalTrackField
from musify.libraries.remote.core.types import RemoteObjectType
from tests.libraries.core.object import TrackTester
from tests.libraries.local.utils import path_track_all, path_track_img, path_track_resources
from tests.libraries.remote.spotify.utils import random_uri
from tests.utils import path_txt, random_str

try:
    from PIL import Image
except ImportError:
    Image = None


async def test_load_fails():
    # raises error on unrecognised file type
    with pytest.raises(InvalidFileType):
        await load_track(path_txt)


def test_loaded_attributes_flac(track_flac: FLAC):
    assert track_flac.tag_sep == "; "

    # metadata
    assert track_flac.title == "title 1"
    assert track_flac.artist == "artist 1"
    assert track_flac.artists == ["artist 1"]
    assert track_flac.album == "album artist 1"
    assert track_flac.album_artist == "various"
    assert track_flac.track_number == 1
    assert track_flac.track_total == 4
    assert track_flac.genres == ["Pop", "Rock", "Jazz"]
    assert track_flac.date == date(2020, 3, 25)
    assert track_flac.year == 2020
    assert track_flac.month == 3
    assert track_flac.day == 25
    assert track_flac.bpm == 120.12
    assert track_flac.key == "A"
    assert track_flac.disc_number == 1
    assert track_flac.disc_total == 3
    assert track_flac.compilation
    # noinspection SpellCheckingInspection
    assert track_flac.comments == ["spotify:track:6fWoFduMpBem73DMLCOh1Z"]

    assert track_flac.uri == track_flac.comments[0]
    assert track_flac.has_uri

    # file properties
    assert int(track_flac.length) == 20
    # assert track.path == path_track_flac  # uses tmp_path instead
    assert track_flac.ext == ".flac"
    assert track_flac.size == 1818191
    assert track_flac.channels == 1
    assert track_flac.bit_rate == 706.413
    assert track_flac.bit_depth == 16
    assert track_flac.sample_rate == 44.1


def test_loaded_attributes_mp3(track_mp3: MP3):
    assert track_mp3.tag_sep == "; "

    # metadata
    assert track_mp3.title == "title 2"
    assert track_mp3.artist == "artist 2; another artist"
    assert track_mp3.artists == ["artist 2", "another artist"]
    assert track_mp3.album == "album artist 2"
    assert track_mp3.album_artist == "various"
    assert track_mp3.track_number == 3
    assert track_mp3.track_total == 4
    assert track_mp3.genres == ["Pop Rock", "Musical"]
    assert track_mp3.date == date(2024, 5, 1)
    assert track_mp3.year == 2024
    assert track_mp3.month == 5
    assert track_mp3.day == 1
    assert track_mp3.bpm == 200.56
    assert track_mp3.key == "C"
    assert track_mp3.disc_number == 2
    assert track_mp3.disc_total == 3
    assert not track_mp3.compilation
    # noinspection SpellCheckingInspection
    assert track_mp3.comments == ["spotify:track:1TjVbzJUAuOvas1bL00TiH"]

    assert track_mp3.uri == track_mp3.comments[0]
    assert track_mp3.has_uri

    # file properties
    assert int(track_mp3.length) == 30
    # assert track.path == path_track_mp3  # uses tmp_path instead
    assert track_mp3.ext == ".mp3"
    assert track_mp3.size == 410910
    assert track_mp3.channels == 1
    assert track_mp3.bit_rate == 96.0
    assert track_mp3.bit_depth is None
    assert track_mp3.sample_rate == 44.1


def test_loaded_attributes_m4a(track_m4a: M4A):
    assert track_m4a.tag_sep == "; "

    # metadata
    assert track_m4a.title == "title 3"
    assert track_m4a.artist == "artist 3"
    assert track_m4a.artists == ["artist 3"]
    assert track_m4a.album == "album artist 3"
    assert track_m4a.album_artist == "various"
    assert track_m4a.track_number == 2
    assert track_m4a.track_total == 4
    assert track_m4a.genres == ["Dance", "Techno"]
    assert track_m4a.date is None
    assert track_m4a.year == 2021
    assert track_m4a.month == 12
    assert track_m4a.day is None
    assert track_m4a.bpm == 120.0
    assert track_m4a.key == "B"
    assert track_m4a.disc_number == 1
    assert track_m4a.disc_total == 2
    assert track_m4a.compilation
    assert track_m4a.comments == ["spotify:track:4npv0xZO9fVLBmDS2XP9Bw"]

    assert track_m4a.uri == track_m4a.comments[0]
    assert track_m4a.has_uri

    # file properties
    assert int(track_m4a.length) == 20
    # assert track.path == path_track_m4a  # uses tmp_path instead
    assert track_m4a.ext == ".m4a"
    assert track_m4a.size == 302199
    assert track_m4a.channels == 2
    assert track_m4a.bit_rate == 98.17
    assert track_m4a.bit_depth == 16
    assert track_m4a.sample_rate == 44.1


def test_loaded_attributes_wma(track_wma: WMA):
    assert track_wma.tag_sep == "; "

    # metadata
    assert track_wma.title == "title 4"
    assert track_wma.artist == "artist 4"
    assert track_wma.artists == ["artist 4"]
    assert track_wma.album == "album artist 4"
    assert track_wma.album_artist == "various"
    assert track_wma.track_number == 4
    assert track_wma.track_total == 4
    assert track_wma.genres == ["Metal", "Rock"]
    assert track_wma.date is None
    assert track_wma.year == 2023
    assert track_wma.month is None
    assert track_wma.day is None
    assert track_wma.bpm == 200.56
    assert track_wma.key == "D"
    assert track_wma.disc_number == 3
    assert track_wma.disc_total == 4
    assert not track_wma.compilation
    assert track_wma.comments == [track_wma._reader.unavailable_uri_dummy]

    assert track_wma.uri is None
    assert not track_wma.has_uri

    # file properties
    assert int(track_wma.length) == 32
    # assert track.path == path_track_wma  # uses tmp_path instead
    assert track_wma.ext == ".wma"
    assert track_wma.size == 1193637
    assert track_wma.channels == 1
    assert track_wma.bit_rate == 96.0
    assert track_wma.bit_depth is None
    assert track_wma.sample_rate == 44.1


def test_loaded_attributes_common(track: LocalTrack):
    assert track.image_links == {}
    assert track.has_image

    # file properties
    assert track.folder == track.path.parent.name
    assert track.filename == track.path.stem
    assert track.type == track.__class__.__name__
    assert track.date_modified == datetime.fromtimestamp(track.path.stat().st_mtime)

    # library properties
    assert track.rating is None
    assert track.date_added is None
    assert track.last_played is None
    assert track.play_count is None

    assert not track._reader.read_images()  # images are always cleared to save memory


class TestLocalTrack(TrackTester):
    """Run generic tests for :py:class:`LocalTrack` implementations"""

    @pytest.fixture
    def item(self, track: LocalTrack) -> MusifyItem:
        return track

    @pytest.fixture
    async def item_unequal(self, track: LocalTrack) -> LocalTrack:
        return next(iter([await load_track(path) for path in path_track_all if path != track.path]))

    @pytest.fixture
    async def item_equal_properties(self, track: LocalTrack) -> LocalTrack:
        track = copy(track)
        track.uri = random_uri(kind=RemoteObjectType.TRACK)
        return track

    @pytest.fixture
    async def item_unequal_properties(self, track: LocalTrack, tmp_path: Path) -> LocalTrack:
        track = copy(track)
        track.title = "new title"
        track.artist = "new artist"
        track.uri = random_uri(kind=RemoteObjectType.TRACK)
        track._path = tmp_path.joinpath("folder", track.path.name)

        return track

    @pytest.fixture
    def item_modified(self, track: LocalTrack) -> MusifyItem:
        track = copy(track)
        track.title = "new title"
        track.artist = "new artist"
        track.uri = random_uri(kind=RemoteObjectType.TRACK)
        return track

    def test_equality_on_path(self, track: LocalTrack, tmp_path: Path):
        track_equal = copy(track)
        track_equal.title = "new title"
        track_equal.artist = "new artist"
        track_equal.uri = random_uri(kind=RemoteObjectType.TRACK)

        assert hash(track) == hash(track_equal)
        assert track_equal == track_equal

        track_unequal = copy(track_equal)
        track_unequal._path = tmp_path.joinpath("folder", track.path.name)

        assert hash(track) != hash(track_unequal)
        assert track != track_unequal

    def test_init_fails(self, track: LocalTrack):
        paths = [path for path in path_track_all if not all(path == ext for ext in track.valid_extensions)]
        with pytest.raises(InvalidFileType):
            for path in paths:
                track.__class__(path)

    async def test_load_track_function(self, track: LocalTrack):
        track_reload = await load_track(track.path)
        assert track_reload.__class__ == track.__class__
        assert track_reload.path == track.path

    async def test_load_track_class(self, track: LocalTrack):
        # has actually reloaded the file
        assert id(track._reader.file) != id(await track.load())

        # raises error on unrecognised file type
        with pytest.raises(InvalidFileType):
            await track.__class__(file=path_txt)

        # raises error on files that do not exist
        with pytest.raises(FileDoesNotExistError):
            await track.__class__(file=f"does_not_exist.{set(track.valid_extensions).pop()}")

    async def test_copy_track(self, track: LocalTrack):
        track_from_file = track.__class__(file=track._reader.file)
        assert id(track._reader.file) == id(track_from_file._reader.file)

        keys = [key for key in track.__slots__ if key.lstrip("_") in dir(track)]

        track.title = "fake title 1"
        track_copy = copy(track)
        assert id(track._reader.file) == id(track_copy._reader.file)
        assert id(track._writer.file) == id(track_copy._writer.file)
        assert track_copy.title != track.title
        for key in keys:
            assert getattr(track, key) == getattr(track_copy, key)

        track_deepcopy = deepcopy(track)
        assert id(track._reader.file) != id(track_deepcopy._reader.file)
        assert id(track._writer.file) != id(track_deepcopy._writer.file)
        assert track_deepcopy.title != track.title

    def test_set_and_find_file_paths(self, track: LocalTrack, tmp_path: Path):
        # add some files with bad names
        ext = next(iter(track.valid_extensions))
        tmp_path.joinpath("._bad_filename").with_suffix(ext).touch(exist_ok=True)
        tmp_path.joinpath(".bad_filename").with_suffix(ext).touch(exist_ok=True)

        # add some files in folders with names
        hidden_folder = tmp_path.joinpath(".good_folder")
        hidden_folder.mkdir(exist_ok=True)
        hidden_folder_file_path = hidden_folder.joinpath("good_file").with_suffix(ext)
        hidden_folder_file_path.touch(exist_ok=True)

        paths = track.__class__.get_filepaths(str(tmp_path))
        assert paths == {track.path, hidden_folder_file_path}

        assert len(track.__class__.get_filepaths(path_track_resources)) == 1

    def test_getitem_dunder_method_on_mapped_field(self, track: LocalTrack):
        assert track[LocalTrackField.TRACK] == track.track_number
        assert track[LocalTrackField.DISC] == track.disc_number
        assert track[LocalTrackField.DATE] == track.date

    def test_setitem_dunder_method(self, track: LocalTrack):
        new_uri = "new_uri"
        assert track.uri != new_uri
        track["uri"] = new_uri
        assert track.uri == new_uri

        new_artist = "artist name"
        assert track.artist != new_artist
        track[LocalTrackField.ARTIST] = new_artist
        assert track.artist == new_artist

        # LocalTrackField.TRACK gives back multiple tags, ensure it sets the track_number only
        new_track_number = track.track_number * 2
        assert track.track_number != new_track_number
        track[LocalTrackField.TRACK] = new_track_number
        assert track.track_number == new_track_number

        with pytest.raises(MusifyKeyError):
            track["bad key"] = "value"

        with pytest.raises(AttributeError):
            track["name"] = "cannot set name"

    async def test_move(self, track: LocalTrack, tmp_path: Path):
        old_path = track.path
        new_path = tmp_path.joinpath("folder", "subfolder", track.path.name)
        assert old_path != new_path
        assert old_path.is_file()
        assert not new_path.is_file()

        await track.move(new_path)

        assert track.path == new_path
        assert track._reader.file.filename == str(new_path)
        assert track._writer.file.filename == str(new_path)

        assert not old_path.is_file()
        assert new_path.is_file()

    async def test_rename(self, track: LocalTrack, tmp_path: Path):
        old_path = track.path
        new_path = tmp_path.parent.joinpath("folder", "subfolder", random_str()).with_suffix(track.ext)
        expected = old_path.with_stem(new_path.stem)

        assert old_path != new_path
        assert old_path.parent != new_path.parent
        assert old_path.is_file()
        assert not new_path.is_file()
        assert not expected.is_file()

        await track.rename(new_path)

        assert track.path != new_path
        assert track.path == expected
        assert track._reader.file.filename == str(expected)
        assert track._writer.file.filename == str(expected)

        assert not old_path.is_file()
        assert not new_path.is_file()
        assert expected.is_file()

    def test_merge(self, track: LocalTrack, item_modified: Track):
        assert track.title != item_modified.title
        assert track.artist != item_modified.artist
        assert track.uri != item_modified.uri
        assert track.album == item_modified.album
        assert track.rating == item_modified.rating

        track.merge(item_modified, tags={LocalTrackField.TITLE, LocalTrackField.URI})
        assert track.title == item_modified.title
        assert track.artist != item_modified.artist
        assert track.uri == item_modified.uri
        assert track.album == item_modified.album
        assert track.rating == item_modified.rating

    def test_merge_dunder_methods(self, track: LocalTrack, item_modified: Track):
        assert track.title != item_modified.title
        assert track.artist != item_modified.artist
        assert track.uri != item_modified.uri
        assert track.album == item_modified.album
        assert track.rating == item_modified.rating

        new_track = track | item_modified
        assert track.title != item_modified.title
        assert track.artist != item_modified.artist
        assert track.uri != item_modified.uri

        assert new_track.title == item_modified.title
        assert new_track.artist == item_modified.artist
        assert new_track.uri == item_modified.uri
        assert new_track.album == item_modified.album
        assert new_track.rating == item_modified.rating

        track |= item_modified
        assert track.title == item_modified.title
        assert track.artist == item_modified.artist
        assert track.uri == item_modified.uri
        assert track.album == item_modified.album
        assert track.rating == item_modified.rating

    def test_extract_images(self, track: LocalTrack, tmp_path: Path):
        # all tracks have an embedded image
        # images should be removed in refresh step, they should then be reloaded during extraction call
        assert not track._reader.read_images()
        assert track.has_image

        def _get_paths():
            img_extensions = {ex for ex, f in Image.registered_extensions().items() if f in Image.OPEN}
            return [path for ext in img_extensions for path in tmp_path.glob(f"*{ext}")]

        assert not _get_paths()
        count = track.extract_images_to_file(tmp_path)
        assert len(_get_paths()) == count > 0

        # deletes loaded images again after running
        assert not track._reader.read_images()


class TestLocalTrackWriter:

    @staticmethod
    def assert_track_tags_equal(actual: LocalTrack, expected: LocalTrack):
        """Assert the tags of the givens tracks equal."""
        assert actual.title == expected.title, "title"
        assert actual.artist == expected.artist, "artist"
        assert actual.album == expected.album, "album"
        assert actual.album_artist == expected.album_artist, "album_artist"
        assert actual.track_number == expected.track_number, "track_number"
        assert actual.track_total == expected.track_total, "track_total"
        assert actual.genres == expected.genres, "genres"

        assert actual.date == expected.date, "date"
        assert actual.year == expected.year, "year"
        if actual.year is not None:
            assert actual.month == expected.month, "month"
        else:
            assert actual.month is None
        if actual.year is not None and actual.month is not None:
            assert actual.day == expected.day, "day"
        else:
            assert actual.day is None

        assert actual.bpm == expected.bpm, "bpm"
        assert actual.key == expected.key, "key"
        assert actual.disc_number == expected.disc_number, "disc_number"
        assert actual.disc_total == expected.disc_total, "disc_total"
        assert actual.compilation == expected.compilation, "compilation"

    @staticmethod
    def assert_track_tags_equal_on_existing(actual: LocalTrack, expected: LocalTrack):
        """Assert the tags of the givens tracks equal only when a mapping for that tag exists."""
        assert not actual.tag_map.title or actual.title == expected.title, "title"
        assert not actual.tag_map.artist or actual.artist == expected.artist, "artist"
        assert not actual.tag_map.album or actual.album == expected.album, "album"
        assert not actual.tag_map.album_artist or actual.album_artist == expected.album_artist, "album_artist"
        assert not actual.tag_map.track_number or actual.track_number == expected.track_number, "track_number"
        assert not actual.tag_map.track_total or actual.track_total == expected.track_total, "track_total"
        assert not actual.tag_map.genres or actual.genres == expected.genres, "genres"
        assert not actual.tag_map.date or actual.date == expected.date, "date"
        assert not actual.tag_map.year or actual.year == expected.year, "year"
        assert not actual.tag_map.month or actual.month == expected.month, "month"
        assert not actual.tag_map.day or actual.day == expected.day, "day"
        assert not actual.tag_map.bpm or actual.bpm == expected.bpm, "bpm"
        assert not actual.tag_map.key or actual.key == expected.key, "key"
        assert not actual.tag_map.disc_number or actual.disc_number == expected.disc_number, "disc_number"
        assert not actual.tag_map.disc_total or actual.disc_total == expected.disc_total, "disc_total"
        assert not actual.tag_map.compilation or actual.compilation == expected.compilation, "compilation"
        assert not actual.tag_map.images or actual.has_image == expected.has_image, "images"

    ###########################################################################
    ## Clear tags
    ###########################################################################
    async def test_clear_tags_dry_run(self, track: LocalTrack):
        track_update = track
        track_original = copy(track)

        # when dry run, no updates should happen
        result = await track_update.delete_tags(tags=LocalTrackField.ALL, dry_run=True)
        assert not result.saved

        # noinspection PyTestUnpassedFixture
        track_update_dry = await load_track(track.path, remote_wrangler=track._reader.remote_wrangler)

        self.assert_track_tags_equal(track_update_dry, track_original)
        assert track_update.comments == track_original.comments

        assert track_update_dry.uri == track_original.uri
        assert track_update_dry.has_uri == track_original.has_uri
        assert track_update_dry.has_image == track_original.has_image

    async def test_clear_tags(self, track: LocalTrack):
        track_update = track
        track_original = copy(track)

        result = await track_update.delete_tags(tags=LocalTrackField.ALL, dry_run=False)
        assert result.saved

        # noinspection PyTestUnpassedFixture
        track_update = await load_track(track.path, remote_wrangler=track._reader.remote_wrangler)

        assert track_update.title is None
        assert track_update.artist is None
        assert track_update.album is None
        assert track_update.album_artist is None
        assert track_update.track_number is None
        assert track_update.track_total is None
        assert track_update.genres is None
        assert track_update.date is None
        assert track_update.year is None
        assert track_update.month is None
        assert track_update.day is None
        assert track_update.bpm is None
        assert track_update.key is None
        assert track_update.disc_number is None
        assert track_update.disc_total is None
        assert not track_update.compilation
        assert track_update.comments is None

        assert track_update.uri is None
        assert track.has_uri == track_original.has_uri
        assert not track_update.has_image

    ###########################################################################
    ## Update standard tags
    ###########################################################################
    @staticmethod
    def get_update_tags_test_track(track: LocalTrack) -> tuple[LocalTrack, LocalTrack, str]:
        """Load track and modify its tags for update tags tests"""
        track_original = copy(track)
        new_uri = track._reader.unavailable_uri_dummy if track.has_uri else random_uri()

        track.title = "new title"
        track.artist = "new artist"
        track.album = "new album artist"
        track.album_artist = "new various"
        track.track_number = 2
        track.track_total = 3
        track.genres = ["Big Band", "Swing"]
        track.year = 1956
        track.month = 4
        track.day = 16
        track.bpm = 98.0
        track.key = "F#"
        track.disc_number = 2
        track.disc_total = 3
        track.compilation = False
        track.uri = new_uri
        track.image_links.clear()

        return track, track_original, new_uri

    async def test_update_tags_dry_run(self, track: LocalTrack):
        track_update, track_original, _ = self.get_update_tags_test_track(track)

        # dry run, no updates should happen
        result = await track_update.save(tags=LocalTrackField.ALL, replace=False, dry_run=True)
        assert not result.saved

        track_on_disk = deepcopy(track_update)

        self.assert_track_tags_equal(track_on_disk, track_original)
        assert track_on_disk.comments == track_original.comments

        assert track_on_disk.uri == track_original.uri
        assert track_on_disk.has_uri == track_original.has_uri
        assert track_on_disk.has_image == track_original.has_image

    async def test_update_tags_no_replace(self, track: LocalTrack):
        track_update, track_original, new_uri = self.get_update_tags_test_track(track)

        # update and don't replace current tags (except URI if URI is False)
        result = await track_update.save(tags=LocalTrackField.ALL, replace=False, dry_run=False)
        assert result.saved

        track_on_disk = deepcopy(track_update)

        self.assert_track_tags_equal(track_on_disk, track_original)
        assert track_on_disk.comments == [new_uri]

        if new_uri == track._reader.unavailable_uri_dummy:
            assert track_on_disk.uri is None
        else:
            assert track_on_disk.uri == new_uri
        assert track_on_disk.has_uri == track_on_disk.has_uri
        assert track_on_disk.has_image == track_original.has_image

    async def test_update_tags_with_replace(self, track: LocalTrack):
        track_update, track_original, new_uri = self.get_update_tags_test_track(track)

        result = await track_update.save(tags=LocalTrackField.ALL, replace=True, dry_run=False)
        assert result.saved

        track_on_disk = deepcopy(track_update)

        self.assert_track_tags_equal_on_existing(track_on_disk, track_update)
        assert track_on_disk.comments == [new_uri]

        if new_uri == track._reader.unavailable_uri_dummy:
            assert track_update.uri is None
        else:
            assert track_update.uri == new_uri
        assert track_on_disk.image_links == track_update.image_links
        assert track_on_disk.has_image == track_update.has_image

    async def test_update_tags_results(self, track: LocalTrack):
        track_original = copy(track)

        track.title = "new title"
        track.album = "new album artist"
        track.track_number += 2
        track.genres = ["Big Band", "Swing"]
        if choice([True, False]):
            track.year = None
            track.bpm += 10
        else:
            track.year += 10
            track.bpm = None
        track.key = "F#"
        track.disc_number += 5

        result = await track.save(tags=LocalTrackField.ALL, replace=True, dry_run=False)
        assert result.saved

        expected_tags = {
            LocalTrackField.TITLE,
            LocalTrackField.ALBUM,
            LocalTrackField.TRACK,
            LocalTrackField.GENRES,
            (LocalTrackField.DATE if track.tag_map.date else LocalTrackField.YEAR),
            LocalTrackField.BPM,
            LocalTrackField.KEY,
            LocalTrackField.DISC,
        }
        assert set(result.updated) == expected_tags

        self.assert_track_tags_equal(copy(track_original), track)

        track.artist = "new artist"
        track.album_artist = "new various"
        track.compilation = not track.compilation

        tags_to_update = {LocalTrackField.ARTIST, LocalTrackField.COMPILATION}
        result = await track.save(tags=tags_to_update, replace=True, dry_run=False)
        assert result.saved
        assert set(result.updated) == tags_to_update

    ###########################################################################
    ## Update images
    ###########################################################################
    @staticmethod
    def get_update_image_test_track(track: LocalTrack) -> tuple[LocalTrack, LocalTrack]:
        """Load track and modify its tags for update tags tests"""
        track.image_links = {"cover front": path_track_img}
        track_copy = copy(track)

        # assign back to ensure tests can load the original image to compare against
        track._reader.file = mutagen.File(track.path)
        track._writer.file = track._reader.file

        return track, track_copy

    @staticmethod
    def assert_update_image_result(track: LocalTrack, image: Image.Image, result: SyncResultTrack):
        """Check for expected results after non-dry_run operations to update LocalTrack images"""
        assert result.saved
        assert deepcopy(track).has_image

        track._reader.file = mutagen.File(track.path)
        images = track._reader.read_images()

        if not isinstance(track, MP3):
            # MP3 tagging works slightly differently so more than one image will be saved
            assert len(images) == 1
        assert images[0].size == image.size

    async def test_update_image_dry_run(self, track: LocalTrack):
        track_original, track_update = self.get_update_image_test_track(track)

        image_original = track_original._reader.read_images()[0]

        # dry run, no updates should happen
        result = await track_update.save(tags=LocalTrackField.IMAGES, replace=False, dry_run=True)
        assert not result.saved

        track_on_disk = deepcopy(track_update)
        assert track_on_disk.has_image == track_original.has_image

        track_update._reader.file = mutagen.File(track_update.path)
        images = track_update._reader.read_images()
        assert len(images) == 1
        assert images[0].size == image_original.size

    async def test_update_image_no_replace(self, track: LocalTrack):
        track_original, track_update = self.get_update_image_test_track(track)

        # clear current image and update
        await track_update.delete_tags(LocalTrackField.IMAGES, dry_run=False)
        assert not track_update.has_image

        result = await track_update.save(tags=LocalTrackField.IMAGES, replace=False, dry_run=False)
        self.assert_update_image_result(track=track_update, image=open_image(path_track_img), result=result)

    async def test_update_image_with_replace(self, track: LocalTrack):
        track_original, track_update = self.get_update_image_test_track(track)

        result = await track_update.save(tags=LocalTrackField.IMAGES, replace=True, dry_run=False)
        self.assert_update_image_result(track=track_update, image=open_image(path_track_img), result=result)

    ###########################################################################
    ## Deferred file move
    ###########################################################################
    @pytest.fixture
    def old_path(self, track: LocalTrack) -> Path:
        return track.path

    @pytest.fixture
    def new_path(self, track: LocalTrack, tmp_path: Path) -> Path:
        new_path = tmp_path.joinpath("folder", "subfolder", random_str()).with_suffix(track.ext)

        assert track.path.is_file()
        assert not new_path.is_file()
        assert track.path != new_path

        return new_path

    @pytest.fixture
    def track_with_staged_path(self, track: LocalTrack, old_path: Path, new_path: Path) -> LocalTrack:
        track.path = new_path
        assert track.path == old_path
        assert old_path.is_file()
        assert not new_path.is_file()

        return track

    async def test_move_file_on_save_dry_run(self, track_with_staged_path: LocalTrack, old_path: Path, new_path: Path):
        tags = choice([LocalTrackField.PATH, LocalTrackField.FOLDER, LocalTrackField.FILENAME, LocalTrackField.ALL])
        result = await track_with_staged_path.save(tags=tags, replace=choice([True, False]), dry_run=True)

        assert track_with_staged_path.path == old_path
        assert old_path.is_file()
        assert not new_path.is_file()

        assert not result.saved
        assert set(result.updated) == {LocalTrackField.PATH}

    async def test_move_file_on_save(self, track_with_staged_path: LocalTrack, old_path: Path, new_path: Path):
        tags = choice([LocalTrackField.PATH, LocalTrackField.FOLDER, LocalTrackField.FILENAME, LocalTrackField.ALL])
        result = await track_with_staged_path.save(tags=tags, replace=choice([True, False]), dry_run=False)

        assert track_with_staged_path.path == new_path
        assert not old_path.is_file()
        assert new_path.is_file()

        assert result.saved
        assert set(result.updated) == {LocalTrackField.PATH}
