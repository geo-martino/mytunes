import pytest

from musify.field import TagFields as Tag
from musify.libraries.local.track import LocalTrack
from musify.processors.match import ItemMatcher, CleanTagConfig
from tests.libraries.local.track.utils import random_track
from tests.testers import PrettyPrinterTester


class TestItemMatcher(PrettyPrinterTester):

    @pytest.fixture
    def obj(self, matcher: ItemMatcher) -> ItemMatcher:
        return matcher

    @pytest.fixture(scope="class")
    def matcher(self) -> ItemMatcher:
        """Return an :py:class:`ItemMatcher` object with expected config for subsequent tests."""
        ItemMatcher.karaoke_tags = {"karaoke", "backing", "instrumental"}
        ItemMatcher.year_range = 10

        ItemMatcher.clean_tags_remove_all = {"the", "a", "&", "and"}
        ItemMatcher.clean_tags_split_all = set()
        ItemMatcher.clean_tags_config = (
            CleanTagConfig(tag=Tag.TITLE, remove={"part"}, split={"featuring", "feat.", "ft.", "/"}),
            CleanTagConfig(tag=Tag.ARTIST, split={"featuring", "feat.", "ft.", "vs"}),
            CleanTagConfig(tag=Tag.ALBUM, remove={"ep"}, preprocess=lambda x: x.split("-")[0])
        )

        ItemMatcher.reduce_name_score_on = {"live", "demo", "acoustic"}
        ItemMatcher.reduce_name_score_factor = 0.5

        return ItemMatcher()

    @pytest.fixture
    def track1(self) -> LocalTrack:
        """Generate a random :py:class:`LocalTrack` for matching"""
        return random_track()

    @pytest.fixture
    def track2(self) -> LocalTrack:
        """Generate a random :py:class:`LocalTrack` for matching"""
        return random_track()

    def test_clean_tags(self, matcher: ItemMatcher, track1: LocalTrack):
        # noinspection SpellCheckingInspection
        track1.uri = "spotify:track:ASDFGHJKLQWERTYUIOPZX"

        track1.title = "A Song Part 2"
        track1.artist = "Artist 1 & Artist two Feat. Artist 3"
        track1.album = "The Best EP - the new one"

        matcher.clean_tags(track1)
        assert track1.clean_tags[Tag.TITLE] == "song 2"
        assert track1.clean_tags[Tag.ARTIST] == "artist 1 artist two"
        assert track1.clean_tags[Tag.ALBUM] == "best"

    def test_match_not_karaoke(self, matcher: ItemMatcher, track1: LocalTrack):
        track1.title = "title"
        track1.artist = "artist"
        track1.album = "album"

        assert matcher.match_not_karaoke(track1, track1) == 1

        track1.title = "title backing"
        assert matcher.match_not_karaoke(track1, track1) == 0

        track1.title = "title"
        track1.album = "album instrumental"
        assert matcher.match_not_karaoke(track1, track1) == 0

    def test_match_name(self, matcher: ItemMatcher, track1: LocalTrack, track2: LocalTrack):
        # no names in at least one item always returns 0
        track1.clean_tags[Tag.NAME] = None
        track2.clean_tags[Tag.NAME] = None
        assert matcher.match_name(track1, track2) == 0

        # 1/1 word match
        track1.title = "title"
        track1.clean_tags[Tag.NAME] = track1.title
        track2.title = "other title"
        track2.clean_tags[Tag.NAME] = track2.title
        assert matcher.match_name(track1, track2) == 1

        # 0/4 words match
        track1.title = "title of a track"
        track1.clean_tags[Tag.NAME] = track1.title
        track2.title = "song"
        track2.clean_tags[Tag.NAME] = track2.title
        assert matcher.match_name(track1, track2) == 0

        # 2/3 words match
        track1.title = "a longer title"
        track1.clean_tags[Tag.NAME] = track1.title
        track2.title = "this is a different title"
        track2.clean_tags[Tag.NAME] = track2.title
        assert round(matcher.match_name(track1, track2), 2) == 0.67

    def test_match_artist(self, matcher: ItemMatcher, track1: LocalTrack, track2: LocalTrack):
        sep = track1.tag_sep

        # no artists in at least one item always returns 0
        track1.clean_tags[Tag.ARTIST] = "artist"
        track2.clean_tags[Tag.ARTIST] = None
        assert matcher.match_artist(track1, track2) == 0

        # 1/4 words match
        track1.clean_tags[Tag.ARTIST] = f"band{sep}a singer{sep}artist"
        track2.clean_tags[Tag.ARTIST] = f"artist{sep}nope{sep}other"
        assert matcher.match_artist(track1, track2) == 0.25

        # 2/4 words match, but now weighted
        # match 'artist' = 0.25 + match 'singer' = 0.125
        track1.clean_tags[Tag.ARTIST] = f"band{sep}a singer{sep}artist"
        track2.clean_tags[Tag.ARTIST] = f"artist{sep}singer{sep}other"
        assert matcher.match_artist(track1, track2) == 0.375

    def test_match_album(self, matcher: ItemMatcher, track1: LocalTrack, track2: LocalTrack):
        # no albums in at least one item always returns 0
        track1.clean_tags[Tag.ALBUM] = None
        track2.clean_tags[Tag.ALBUM] = "album"
        assert matcher.match_album(track1, track2) == 0

        # 1/2 words match
        track1.clean_tags[Tag.ALBUM] = "album name"
        track2.clean_tags[Tag.ALBUM] = "name"
        assert matcher.match_album(track1, track2) == 0.5

        # 3/3 words match
        track1.clean_tags[Tag.ALBUM] = "brand new album"
        track2.clean_tags[Tag.ALBUM] = "this is a brand new really cool album"
        assert matcher.match_album(track1, track2) == 1

    def test_match_length(self, matcher: ItemMatcher, track1: LocalTrack, track2: LocalTrack):
        # no lengths for at least one item always returns 0
        track1.clean_tags[Tag.LENGTH] = 110.20
        track2.clean_tags[Tag.LENGTH] = None
        assert matcher.match_length(track1, track2) == 0

        track1.clean_tags[Tag.LENGTH] = 100
        track2.clean_tags[Tag.LENGTH] = 90
        assert matcher.match_length(track1, track2) == 0.9

    def test_match_year(self, matcher: ItemMatcher, track1: LocalTrack, track2: LocalTrack):
        # no year for at least one item always returns 0
        track1.clean_tags[Tag.YEAR] = 2023
        track2.clean_tags[Tag.YEAR] = None
        assert matcher.match_year(track1, track2) == 0

        track1.clean_tags[Tag.YEAR] = 2020
        track2.clean_tags[Tag.YEAR] = 2015
        assert matcher.match_year(track1, track2) == 0.5

        track1.clean_tags[Tag.YEAR] = 2020
        track2.clean_tags[Tag.YEAR] = 2010
        assert matcher.match_year(track1, track2) == 0

        track1.clean_tags[Tag.YEAR] = 2020
        track2.clean_tags[Tag.YEAR] = 2005
        assert matcher.match_year(track1, track2) == 0

    @pytest.mark.slow
    def test_match_all(self, matcher: ItemMatcher, track1: LocalTrack, track2: LocalTrack):
        sep = track1.tag_sep

        track1.title = "a longer title"
        track2.title = "this is a different title"
        track1.artist = f"band{sep}a singer{sep}artist"
        track2.artist = "nope"
        track1.album = "album"
        track2.album = "name"
        track1._reader.file.info.length = 100
        track2._reader.file.info.length = 10
        track1.year = 2020
        track2.year = 2010

        # track2 score is below min_score
        assert matcher.match(track1, [track2], min_score=0.2, max_score=0.8) is None
        assert matcher(track1, [track2], min_score=0.2, max_score=0.8) is None

        # track3 score is above min_score
        track3 = random_track()
        track3.title = "this is a different title"
        track3.artist = f"artist{sep}nope{sep}other"
        track3.year = 2015
        assert matcher.match(track1, [track2, track3], min_score=0.2, max_score=0.8) == track3
        assert matcher(track1, [track3, track2], min_score=0.2, max_score=0.8) == track3

        # track4 score is above max_score causing an early stop
        track4 = random_track()
        track4.title = "a longer title"
        track4.artist = f"band{sep}a singer{sep}artist"
        track4.album = "album"
        track4._reader.file.info.length = 100
        track4.year = 2015
        assert matcher.match(track1, [track4, track2, track3], min_score=0.2, max_score=0.8) == track4
        assert matcher(track1, [track2, track4, track3], min_score=0.2, max_score=0.8) == track4

    def test_allows_karaoke(self, matcher: ItemMatcher, track1: LocalTrack, track2: LocalTrack):
        sep = track1.tag_sep
        track3 = random_track()

        track1.title = "a longer title"
        track2.title = "this is track2 title"
        track3.title = "this is track3 title"

        track1.artist = f"band{sep}a singer{sep}artist"
        track2.artist = "nope"
        track3.artist = f"artist{sep}nope{sep}other"

        track1.album = "album"
        track2.album = "name"
        track3.album = "valid album"

        track1._reader.file.info.length = 100
        track2._reader.file.info.length = 10
        track3._reader.file.info.length = 100

        track1.year = 2020
        track2.year = 2010
        track3.year = 2020

        # track3 score is above min_score
        assert matcher.match(track1, [track2, track3], min_score=0.5, max_score=1) == track3

        # ...but is now karaoke
        track3.album = "karaoke"
        assert matcher.match(track1, [track2, track3], min_score=0.5, max_score=1) is None

        # ...and now karaoke is allowed
        assert matcher(track1, [track2, track3], min_score=0.5, max_score=1, allow_karaoke=True) == track3
