from datetime import datetime, timedelta
from pathlib import Path

import pytest
from faker import Faker
from mytunes._models.properties.length import Length
from mytunes.local._item.album import LocalAlbum
from mytunes.local._item.track import LocalTrack
from mytunes.processors.limit import ItemLimiter, LimitType
from tests.processors.utils import create_random_file
from tests.testers import BaseModelTester


class TestItemLimiter(BaseModelTester):

    @pytest.fixture
    def model(self) -> ItemLimiter:
        return ItemLimiter(limit_by=30, on=LimitType.MINUTES, sorted_by="HighestRating", allowance=2)

    @pytest.fixture
    def tracks(self, local_tracks: list[LocalTrack]) -> list[LocalTrack]:
        """Yields a list of random tracks with dynamically configured properties for limit tests"""
        for i in range(1, 6):
            album = LocalAlbum(name=f"album {i}")

            for track in local_tracks[(i-1)*10:i*10]:
                track.album = album
                track.__dict__["length"] = Length(i * 60)
                track.rating = i
                track.last_played_at = datetime.now() if i != 1 and i != 5 else datetime.now() - timedelta(days=1)
                track.play_count = 1000000 if i == 1 or i == 3 else 0

        return local_tracks

    @pytest.fixture
    def tracks_with_sizes(self, tracks: list[LocalTrack], faker: Faker, tmp_path: Path) -> list[LocalTrack]:
        """Yields a list of random tracks with files generated to test for size limiting"""
        for i in range(1, 6):
            for track in tracks[(i-1)*10:i*10]:
                track.path = tmp_path.joinpath(faker.file_path(depth=i, absolute=False, extension="mp3"))
                create_random_file(track.path, size=i * 1000)

        return tracks

    def test_init(self):
        limiter = ItemLimiter(sorted_by="HighestRating")
        assert limiter.sorted_by == "highest_rating"
        assert limiter._processor_method == limiter._highest_rating

        limiter = ItemLimiter(sorted_by="__ least_recently_added __ ")
        assert limiter.sorted_by == "least_recently_added"
        assert limiter._processor_method == limiter._least_recently_added

        limiter = ItemLimiter(sorted_by="__most recently played__")
        assert limiter.sorted_by == "most_recently_played"
        assert limiter._processor_method == limiter._most_recently_played

    def test_limit_below_threshold(self, tracks: list[LocalTrack]):
        assert len(tracks) == 50

        limiter = ItemLimiter()
        limiter.limit(tracks)
        assert len(tracks) == 50

        limiter = ItemLimiter(limit_by=len(tracks) + 10, on=LimitType.ITEMS)
        limiter.limit(tracks)
        assert len(tracks) == 50

    def test_limit_ignores_items(self, tracks: list[LocalTrack]):
        ignore = [track for track in tracks if track.album.name == "album 5"]
        assert ignore and tracks[0] not in ignore

        limiter = ItemLimiter(limit_by=1)
        limiter.limit(tracks, ignore=ignore)
        assert len(tracks) == 1 + len(ignore)

    def test_limit_on_items_1(self, tracks: list[LocalTrack]):
        limiter = ItemLimiter(limit_by=25)
        limiter.limit(tracks)
        assert len(tracks) == 25

    def test_limit_on_items_2(self, tracks: list[LocalTrack]):
        limiter = ItemLimiter(limit_by=10, sorted_by="HighestRating")
        limiter.limit(tracks)
        assert len(tracks) == 10
        assert {track.album.name for track in tracks} == {"album 5"}

    def test_limit_on_items_3(self, tracks: list[LocalTrack]):
        limiter = ItemLimiter(limit_by=20, sorted_by="most often played")
        limiter.limit(tracks)
        assert len(tracks) == 20
        assert {track.album.name for track in tracks} == {"album 1", "album 3"}

    def test_limit_on_albums_1(self, tracks: list[LocalTrack]):
        limiter = ItemLimiter(limit_by=3, on=LimitType.ALBUMS)
        limiter.limit(tracks)
        assert len(tracks) == 30

    def test_limit_on_albums_2(self, tracks: list[LocalTrack]):
        limiter = ItemLimiter(limit_by=2, on=LimitType.ALBUMS, sorted_by="least recently played")
        limiter.limit(tracks)
        assert len(tracks) == 20
        assert {track.album.name for track in tracks} == {"album 1", "album 5"}

    def test_limit_on_seconds_1(self, tracks: list[LocalTrack]):
        limiter = ItemLimiter(limit_by=30, on=LimitType.MINUTES)
        limiter.limit(tracks)
        assert len(tracks) == 20

    def test_limit_on_seconds_2(self, tracks: list[LocalTrack]):
        limiter = ItemLimiter(limit_by=30, on=LimitType.MINUTES, allowance=2)
        limiter.limit(tracks)
        assert len(tracks) == 21

    def test_limit_on_bytes_1(self, tracks_with_sizes: list[LocalTrack]):
        limiter = ItemLimiter(limit_by=30, on=LimitType.KILOBYTES)
        limiter.limit(tracks_with_sizes)
        assert len(tracks_with_sizes) == 20

    def test_limit_on_bytes_2(self, tracks_with_sizes: list[LocalTrack]):
        limiter = ItemLimiter(limit_by=30, on=LimitType.KILOBYTES, allowance=2)
        limiter.limit(tracks_with_sizes)
        assert len(tracks_with_sizes) == 21
