from collections.abc import Callable
from itertools import groupby
from random import choice, randrange, shuffle, sample

import pytest

from musify.field import TrackField
from musify.libraries.local.track import LocalTrack
from musify.libraries.local.track.field import LocalTrackField
from musify.processors.sort import ItemSorter, ShuffleMode
from musify.utils import strip_ignore_words
from tests.libraries.local.track.utils import random_tracks
from tests.testers import PrettyPrinterTester


class TestItemSorter(PrettyPrinterTester):

    @pytest.fixture
    def obj(self) -> ItemSorter:
        return ItemSorter(fields=[TrackField.ALBUM, TrackField.DISC, TrackField.TRACK])

    @pytest.fixture(scope="class")
    def tracks(self) -> list[LocalTrack]:
        """Generate a list of random tracks with dynamically configured properties for sort tests"""
        tracks = random_tracks(30)
        for i, track in enumerate(tracks, 1):
            track.album = choice(["album 1", "album 2"])
            track.track_number = i
            track.track_total = len(tracks)
            track.disc_number = randrange(1, 3)
            track.date_added = track.date_added.replace(second=i)

        shuffle(tracks)
        return tracks

    def test_sort_by_field_basic(self, tracks: list[LocalTrack]):
        # no shuffle and reverse
        tracks_original = tracks.copy()
        ItemSorter.sort_by_field(tracks)
        assert tracks == tracks_original
        ItemSorter.sort_by_field(tracks, reverse=True)
        assert tracks == tracks_original[::-1]

    def test_sort_by_track_number(self, tracks: list[LocalTrack]):
        tracks_sorted = sorted(tracks, key=lambda t: t.track_number)
        ItemSorter.sort_by_field(tracks, field=TrackField.TRACK)
        assert tracks == tracks_sorted
        ItemSorter.sort_by_field(tracks, field=TrackField.TRACK, reverse=True)
        assert tracks == tracks_sorted[::-1]

    def test_sort_by_date_added(self, tracks: list[LocalTrack]):
        tracks_sorted = sorted(tracks, key=lambda t: t.date_added)
        ItemSorter.sort_by_field(tracks, field=LocalTrackField.DATE_ADDED)
        assert tracks == tracks_sorted
        ItemSorter.sort_by_field(tracks, field=LocalTrackField.DATE_ADDED, reverse=True)
        assert tracks == tracks_sorted[::-1]

    def test_sort_by_title_with_ignore_words(self, tracks: list[LocalTrack]):
        ignore_words = ("This", "and", "that")
        for track in sample(tracks, k=len(tracks) // 2):
            track.title = f"{choice(ignore_words)} {track.title}"

        def _sort_key(t: LocalTrack) -> tuple[bool, str]:
            not_special_start, value = strip_ignore_words(t.title, words=ignore_words)
            return not_special_start, value.lower()

        tracks_sorted = sorted(tracks, key=_sort_key)
        ItemSorter.sort_by_field(tracks, field=TrackField.TITLE, ignore_words=ignore_words)
        assert tracks == tracks_sorted
        ItemSorter.sort_by_field(tracks, field=TrackField.TITLE, reverse=True, ignore_words=ignore_words)
        assert tracks == tracks_sorted[::-1]

    def test_group_by_field(self, tracks: list[LocalTrack]):
        assert ItemSorter.group_by_field(tracks) == {None: tracks}

        groups = ItemSorter.group_by_field(tracks, TrackField.KEY)
        assert sorted(groups) == sorted({track.key for track in tracks})
        assert sum(map(len, groups.values())) == len(tracks)

    def test_shuffle_random(self, tracks: list[LocalTrack]):

        tracks_original = tracks.copy()
        ItemSorter().sort(tracks)
        assert tracks == tracks_original
        ItemSorter(shuffle_mode=ShuffleMode.RANDOM).sort(tracks)
        assert tracks != tracks_original

        def _sort_key(t: LocalTrack) -> tuple[bool, str]:
            not_special_start, value = strip_ignore_words(t.title)
            return not_special_start, value.lower()

        # shuffle settings ignored when ``fields`` are defined
        ItemSorter(fields=TrackField.TITLE, shuffle_mode=ShuffleMode.RANDOM).sort(tracks)
        assert tracks == sorted(tracks, key=_sort_key)

    def test_shuffle_rating(self, tracks: list[LocalTrack]):
        assert tracks != sorted(tracks, key=lambda t: t.rating, reverse=True)

        # shuffle_weight == 0 should just sort the tracks in order of rating
        ItemSorter(shuffle_mode=ShuffleMode.HIGHER_RATING).sort(tracks)
        assert tracks == sorted(tracks, key=lambda t: t.rating, reverse=True)

        # positive shuffle weights should give the highest rated track first always
        ItemSorter(shuffle_mode=ShuffleMode.HIGHER_RATING, shuffle_weight=1).sort(tracks)
        max_rating = max(track.rating for track in tracks)
        assert tracks[0].rating == max_rating

        # negative shuffle weights reverse the order
        ItemSorter(shuffle_mode=ShuffleMode.HIGHER_RATING, shuffle_weight=-1).sort(tracks)
        assert tracks[-1].rating == max_rating

        # as shuffle operations are random and therefore difficult to accurately test,
        # just check that the sorted list is not ordered by rating
        ItemSorter(shuffle_mode=ShuffleMode.HIGHER_RATING, shuffle_weight=0.8).sort(tracks)
        assert tracks != sorted(tracks, key=lambda t: t.rating, reverse=True)

    def test_shuffle_date_added(self, tracks: list[LocalTrack]):
        assert tracks != sorted(tracks, key=lambda t: t.date_added, reverse=True)

        # shuffle_weight == 0 should just sort the tracks in order of date added
        ItemSorter(shuffle_mode=ShuffleMode.RECENT_ADDED).sort(tracks)
        assert tracks == sorted(tracks, key=lambda t: t.date_added, reverse=True)

        # positive shuffle weights should give the most recently added track first always
        ItemSorter(shuffle_mode=ShuffleMode.RECENT_ADDED, shuffle_weight=1).sort(tracks)
        max_date_added = max(track.date_added for track in tracks)
        assert tracks[0].date_added == max_date_added

        # negative shuffle weights reverse the order
        ItemSorter(shuffle_mode=ShuffleMode.RECENT_ADDED, shuffle_weight=-1).sort(tracks)
        assert tracks[-1].date_added == max_date_added

        # as shuffle operations are random and therefore difficult to accurately test,
        # just check that the sorted list is not ordered by date added
        ItemSorter(shuffle_mode=ShuffleMode.RECENT_ADDED, shuffle_weight=0.8).sort(tracks)
        assert tracks != sorted(tracks, key=lambda t: t.date_added, reverse=True)

    def test_shuffle_artist(self, tracks: list[LocalTrack]):
        possible_artists = ["artist 1", "artist 2", "artist 3"]
        assert len(tracks) > len(possible_artists) * 5
        for track in tracks:
            track.artist = choice(possible_artists)

        def get_artist_groups(t: list[LocalTrack]) -> list[str]:
            """Gets a list of artists in the order of the distinct groups in the list of given tracks."""
            ar = []
            for tr in t:
                if len(ar) == 0 or tr.artist != ar[-1]:
                    ar.append(tr.artist)

            return ar

        assert len(get_artist_groups(tracks)) != len(possible_artists)

        # shuffle_weight == 1 should sort such that all items are grouped by artist
        ItemSorter(shuffle_mode=ShuffleMode.DIFFERENT_ARTIST, shuffle_weight=1).sort(tracks)
        assert len(get_artist_groups(tracks)) == len(possible_artists)

        # shuffle_weight == -1 should sort such that all items are in order of different artist
        ItemSorter(shuffle_mode=ShuffleMode.DIFFERENT_ARTIST, shuffle_weight=-1).sort(tracks)
        assert len(get_artist_groups(tracks)) > len(tracks) // 3 > len(possible_artists)  # mostly random

        # as shuffle operations are random and therefore difficult to accurately test,
        # just check that the sorted list is not grouped by artist
        ItemSorter(shuffle_mode=ShuffleMode.DIFFERENT_ARTIST, shuffle_weight=0.3).sort(tracks)
        assert len(get_artist_groups(tracks)) != len(possible_artists)

    def test_multi_sort(self, tracks: list[LocalTrack]):
        tracks_sorted = sorted(tracks, key=lambda t: (t.album, t.disc_number, t.track_number))
        sorter = ItemSorter(fields=[TrackField.ALBUM, TrackField.DISC, TrackField.TRACK])
        sorter(tracks)
        assert tracks == tracks_sorted

        # complex multi-sort, includes reverse options
        tracks_sorted = []
        sort_key_1: Callable[[LocalTrack], str] = lambda t: t.album
        for _, group_1 in groupby(sorted(tracks, key=sort_key_1, reverse=True), key=sort_key_1):
            sort_key_2: Callable[[LocalTrack], int] = lambda t: t.disc_number
            for __, group_2 in groupby(sorted(group_1, key=sort_key_2), key=sort_key_2):
                sort_key_3: Callable[[LocalTrack], int] = lambda t: t.track_number
                for ___, group_3 in groupby(sorted(group_2, key=sort_key_3, reverse=True), key=sort_key_3):
                    tracks_sorted.extend(list(group_3))

        fields = {TrackField.ALBUM: True, TrackField.DISC: False, TrackField.TRACK: True}
        sorter = ItemSorter(fields=fields)
        sorter(tracks)
        assert tracks == tracks_sorted
