from collections.abc import Callable, Iterable
from datetime import datetime
from itertools import groupby
from random import choice, shuffle, sample

import pytest
from faker import Faker

from mytunes._models.properties.order import Position
from mytunes.local._item.album import LocalAlbum
from mytunes.local._item.track import LocalTrack
from mytunes.processors.sort import ItemSorter, ShuffleMode
from tests.testers import BaseModelTester


class TestItemSorter(BaseModelTester):

    @pytest.fixture
    def model(self) -> ItemSorter:
        return ItemSorter(sort_fields=["album", "disc", "track"])

    @pytest.fixture
    def tracks(self, local_tracks: list[LocalTrack], faker: Faker) -> list[LocalTrack]:
        """Generate a list of random tracks with dynamically configured properties for sort tests"""
        albums = [LocalAlbum(name="album 1"), LocalAlbum(name="album 2")]
        dt = datetime.now()

        for i, track in enumerate(local_tracks, 1):
            track.album = choice(albums)
            track.track = Position(number=i, total=len(local_tracks))
            track.disc = Position(number=faker.random_int(1, 3))
            track.added_at = dt.replace(second=i)
            track.rating = faker.random_int(100, 500) / 100

        shuffle(local_tracks)
        return local_tracks

    ignore_words = ("This", "and", "that")

    @pytest.fixture
    def tracks_with_ignore_words(self, tracks: list[LocalTrack]) -> list[LocalTrack]:
        for track in sample(tracks, k=len(tracks) // 2):
            track.name = f"{choice(self.ignore_words)} {track.name}"
            track.album = LocalAlbum(name=f"{choice(self.ignore_words)} {track.album.name}")
        return tracks

    @staticmethod
    def _sort_key_for_name(ignore_words: Iterable[str] = ()) -> Callable[[LocalTrack], tuple[bool, str]]:
        def _sort_key(track: LocalTrack) -> tuple[bool, str]:
            value = track.name
            special_start = ItemSorter._special_start(value)
            value = ItemSorter._strip_words(value, words=ignore_words)
            return not special_start, value.casefold()

        return _sort_key

    @staticmethod
    def _sort_key_for_album(ignore_words: Iterable[str] = ()) -> Callable[[LocalTrack], tuple[bool, str]]:
        def _sort_key(track: LocalTrack) -> tuple[bool, str]:
            value = track.album.name
            special_start = ItemSorter._special_start(value)
            value = ItemSorter._strip_words(value, words=ignore_words)
            return not special_start, value.casefold()

        return _sort_key

    def test_sort_by_field_basic(self, tracks: list[LocalTrack]):
        # no shuffle and reverse
        tracks_original = tracks.copy()
        ItemSorter.sort_by_field(tracks)
        assert tracks == tracks_original
        ItemSorter.sort_by_field(tracks, reverse=True)
        assert tracks == tracks_original[::-1]

    def test_sort_by_field_with_missing_values(self, tracks: list[LocalTrack], faker: Faker):
        for track in sample(tracks, k=len(tracks) // 3):
            track.play_count = choice([None, faker.random_int()])

        tracks_sorted = sorted(tracks, key=lambda t: t.play_count or 0)
        ItemSorter.sort_by_field(tracks, field="play_count")
        assert tracks == tracks_sorted

    def test_sort_by_track_number(self, tracks: list[LocalTrack]):
        tracks_sorted = sorted(tracks, key=lambda t: t.track.number)
        ItemSorter.sort_by_field(tracks, field="track")
        assert tracks == tracks_sorted
        ItemSorter.sort_by_field(tracks, field="track", reverse=True)
        assert tracks == tracks_sorted[::-1]

    def test_sort_by_added_at(self, tracks: list[LocalTrack]):
        tracks_sorted = sorted(tracks, key=lambda t: t.added_at)
        ItemSorter.sort_by_field(tracks, field="added_at")
        assert tracks == tracks_sorted
        ItemSorter.sort_by_field(tracks, field="added_at", reverse=True)
        assert tracks == tracks_sorted[::-1]

    def test_sort_by_name_with_ignore_words(self, tracks_with_ignore_words: list[LocalTrack]):
        tracks_sorted = sorted(tracks_with_ignore_words, key=self._sort_key_for_name(self.ignore_words))
        ItemSorter.sort_by_field(tracks_with_ignore_words, field="name", ignore_words=self.ignore_words)
        assert tracks_with_ignore_words == tracks_sorted

    def test_sort_by_album_with_ignore_words(self, tracks_with_ignore_words: list[LocalTrack]):
        tracks_sorted = sorted(tracks_with_ignore_words, key=self._sort_key_for_album(self.ignore_words))
        ItemSorter(sort_fields="album", ignore_words=self.ignore_words).sort(tracks_with_ignore_words)
        assert tracks_with_ignore_words == tracks_sorted

    def test_sort_by_name_with_ignore_words_reversed(self, tracks_with_ignore_words: list[LocalTrack]):
        tracks_sorted = sorted(tracks_with_ignore_words, key=self._sort_key_for_name(self.ignore_words), reverse=True)
        ItemSorter.sort_by_field(tracks_with_ignore_words, field="name", reverse=True, ignore_words=self.ignore_words)
        assert tracks_with_ignore_words == tracks_sorted

    def test_sort_by_album_with_ignore_words_reversed(self, tracks_with_ignore_words: list[LocalTrack]):
        tracks_sorted = sorted(tracks_with_ignore_words, key=self._sort_key_for_album(self.ignore_words), reverse=True)
        ItemSorter(sort_fields={"album": True}, ignore_words=self.ignore_words).sort(tracks_with_ignore_words)
        assert tracks_with_ignore_words == tracks_sorted

    def test_group_by_field(self, tracks: list[LocalTrack]):
        expected_keys = {str(track.disc) for track in tracks}
        assert len(expected_keys) > 1

        groups = ItemSorter.group_by_field(tracks, "disc")
        assert groups.keys() == expected_keys
        assert sum(map(len, groups.values())) == len(tracks)

    def test_group_by_field_with_ignore_words(self, tracks_with_ignore_words: list[LocalTrack]):
        sort_keys = map(self._sort_key_for_album(self.ignore_words), tracks_with_ignore_words)
        expected = {key[-1] for key in sort_keys}

        groups = ItemSorter.group_by_field(tracks_with_ignore_words, "album", ignore_words=self.ignore_words)
        assert groups.keys() == expected
        assert sum(map(len, groups.values())) == len(tracks_with_ignore_words)

    def test_strip_words(self):
        # strip special
        assert ItemSorter._strip_words("!special1", ["special"]) == "special1"
        assert ItemSorter._strip_words("*%2I am very special!", ["very", "i"]) == "2I am very special!"

        # marks as special as needed and strips words
        assert ItemSorter._strip_words("I am a string", ["i"]) == "am a string"
        assert ItemSorter._strip_words("*%I   am very special!", ["am", "i"]) == "am very special!"

        # skip strip special chars
        name = "(help) me please"
        assert ItemSorter._strip_words(name, ["help"], strip_special_chars=False) == name
        assert ItemSorter._strip_words(name, ["help"], strip_special_chars=True) == "me please"

    def test_flatten_groups(self):
        # flattens non-nested
        assert ItemSorter._flatten_groups({"a": 1, "b": 2, "c": 3}) == [1, 2, 3]
        assert ItemSorter._flatten_groups({"a": 1, "b": [2, 3, 4], "c": 5}) == [1, 2, 3, 4, 5]

        # flattens nested
        nested_map = {"a": 1, "b": [2, 3, 4], "c": {"sub1": 5, "sub2": [6], "sub3": {"deep": [7, 8]}}}
        assert ItemSorter._flatten_groups(nested_map) == [1, 2, 3, 4, 5, 6, 7, 8]
        assert ItemSorter._flatten_groups(nested_map, ["a", "b"]) == ["a", "b", 1, 2, 3, 4, 5, 6, 7, 8]

    def test_shuffle_random(self, tracks: list[LocalTrack]):
        tracks_original = tracks.copy()
        ItemSorter().sort(tracks)
        assert tracks == tracks_original

        model = ItemSorter(shuffle_mode=ShuffleMode.RANDOM)
        model.sort(tracks)
        assert tracks != tracks_original

        # shuffle settings ignored when ``fields`` are defined
        model = ItemSorter(sort_fields="name", shuffle_mode=ShuffleMode.RANDOM)
        model.sort(tracks)
        assert tracks == sorted(tracks, key=self._sort_key_for_name(model.ignore_words))

    def test_shuffle_rating(self, tracks: list[LocalTrack]):
        assert tracks != sorted(tracks, key=lambda t: t.rating or 0, reverse=True)

        # shuffle_weight == 0 should just sort the tracks in order of rating
        ItemSorter(shuffle_mode=ShuffleMode.HIGHER_RATING).sort(tracks)
        assert tracks == sorted(tracks, key=lambda t: t.rating or 0, reverse=True)

        # positive shuffle weights should give the highest rated track first always
        ItemSorter(shuffle_mode=ShuffleMode.HIGHER_RATING, shuffle_weight=1).sort(tracks)
        max_rating = max(track.rating or 0 for track in tracks)
        assert tracks[0].rating == max_rating

        # negative shuffle weights reverse the order
        ItemSorter(shuffle_mode=ShuffleMode.HIGHER_RATING, shuffle_weight=-1).sort(tracks)
        assert tracks[-1].rating == max_rating

        # as shuffle operations are random and therefore difficult to accurately test,
        # just check that the sorted list is not ordered by rating
        ItemSorter(shuffle_mode=ShuffleMode.HIGHER_RATING, shuffle_weight=0.8).sort(tracks)
        assert tracks != sorted(tracks, key=lambda t: t.rating, reverse=True)

    def test_shuffle_added_at(self, tracks: list[LocalTrack]):
        assert tracks != sorted(tracks, key=lambda t: t.added_at, reverse=True)

        # shuffle_weight == 0 should just sort the tracks in order of date added
        ItemSorter(shuffle_mode=ShuffleMode.RECENT_ADDED).sort(tracks)
        assert tracks == sorted(tracks, key=lambda t: t.added_at, reverse=True)

        # positive shuffle weights should give the most recently added track first always
        ItemSorter(shuffle_mode=ShuffleMode.RECENT_ADDED, shuffle_weight=1).sort(tracks)
        max_added_at = max(track.added_at for track in tracks)
        assert tracks[0].added_at == max_added_at

        # negative shuffle weights reverse the order
        ItemSorter(shuffle_mode=ShuffleMode.RECENT_ADDED, shuffle_weight=-1).sort(tracks)
        assert tracks[-1].added_at == max_added_at

        # as shuffle operations are random and therefore difficult to accurately test,
        # just check that the sorted list is not ordered by date added
        ItemSorter(shuffle_mode=ShuffleMode.RECENT_ADDED, shuffle_weight=0.8).sort(tracks)
        assert tracks != sorted(tracks, key=lambda t: t.added_at, reverse=True)

    def test_shuffle_artist(self, tracks: list[LocalTrack]):
        artist_names = ["artist 1", "artist 2", "artist 3"]
        assert len(tracks) > len(artist_names) * 5
        for track in tracks:
            track.artist = choice(artist_names)

        def get_artist_groups(t: list[LocalTrack]) -> list[str]:
            """Gets a list of artists in the order of the distinct groups in the list of given tracks."""
            ar = []
            for tr in t:
                if len(ar) == 0 or tr.artist != ar[-1]:
                    ar.append(tr.artist)

            return ar

        assert len(get_artist_groups(tracks)) != len(artist_names)

        # shuffle_weight == 1 should sort such that all items are grouped by artist
        ItemSorter(shuffle_mode=ShuffleMode.DIFFERENT_ARTIST, shuffle_weight=1).sort(tracks)
        assert len(get_artist_groups(tracks)) == len(artist_names)

        # shuffle_weight == -1 should sort such that all items are in order of different artist
        ItemSorter(shuffle_mode=ShuffleMode.DIFFERENT_ARTIST, shuffle_weight=-1).sort(tracks)
        assert len(get_artist_groups(tracks)) > len(tracks) // 3 > len(artist_names)  # mostly random

        # as shuffle operations are random and therefore difficult to accurately test,
        # just check that the sorted list is not grouped by artist
        ItemSorter(shuffle_mode=ShuffleMode.DIFFERENT_ARTIST, shuffle_weight=0.3).sort(tracks)
        assert len(get_artist_groups(tracks)) != len(artist_names)

    def test_multi_sort(self, tracks: list[LocalTrack]):
        tracks_sorted = sorted(tracks, key=lambda t: (t.album, t.disc.number, t.track.number))
        sorter = ItemSorter(sort_fields=["album", "disc", "track"])
        sorter.sort(tracks)
        assert tracks == tracks_sorted

        # complex multi-sort, includes reverse options
        tracks_sorted = []
        sort_key_1: Callable[[LocalTrack], str] = lambda t: t.album
        for key_1, group_1 in groupby(sorted(tracks, key=sort_key_1, reverse=True), key=sort_key_1):
            sort_key_2: Callable[[LocalTrack], int] = lambda t: t.disc.number
            for key_2, group_2 in groupby(sorted(group_1, key=sort_key_2), key=sort_key_2):
                sort_key_3: Callable[[LocalTrack], int] = lambda t: t.track.number
                for key_3, group_3 in groupby(sorted(group_2, key=sort_key_3, reverse=True), key=sort_key_3):
                    tracks_sorted.extend(list(group_3))

        fields = {"album": True, "disc": False, "track": True}
        sorter = ItemSorter(sort_fields=fields)
        sorter.sort(tracks)

        assert tracks == tracks_sorted
