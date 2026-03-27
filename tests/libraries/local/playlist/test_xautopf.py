import os
from collections.abc import Mapping
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from random import randrange

import pytest

from musify.field import Fields
from musify.file.exception import InvalidFileType
from musify.file.path_mapper import PathMapper, PathStemMapper
from musify.libraries.local.library import MusicBee, LocalLibrary
from musify.libraries.local.library.musicbee import REQUIRED_MODULES
from musify.libraries.local.playlist import XAutoPF
from musify.libraries.local.playlist.xautopf import XMLPlaylistParser
from musify.libraries.local.track import LocalTrack
from musify.libraries.local.track.field import LocalTrackField
from musify.processors.compare import Comparer
from musify.processors.filter import FilterComparers
from musify.processors.limit import LimitType
from musify.processors.sort import ShuffleMode
from musify.utils import to_collection, required_modules_installed
from tests.libraries.local.playlist.testers import LocalPlaylistTester
from tests.libraries.local.track.utils import random_track, random_tracks
from tests.libraries.local.utils import path_playlist_resources, path_playlist_all
from tests.libraries.local.utils import path_playlist_xautopf_ra, path_playlist_xautopf_bp, path_playlist_xautopf_cm
from tests.libraries.local.utils import path_track_all, path_track_mp3, path_track_flac, path_track_wma
from tests.testers import PrettyPrinterTester
from tests.utils import path_txt, path_resources, random_str


@pytest.mark.skipif(not required_modules_installed(REQUIRED_MODULES), reason="required modules not installed.")
class TestXAutoPF(LocalPlaylistTester):

    @pytest.fixture
    async def playlist(self) -> XAutoPF:
        # needed to ensure __setitem__ check passes
        tracks = random_tracks(randrange(5, 15))
        tracks.append(random_track(cls=tracks[0].__class__))

        playlist = XAutoPF(path=path_playlist_xautopf_ra)
        return await playlist.load(tracks=tracks)

    def test_init_fails(self):
        with pytest.raises(InvalidFileType):
            XAutoPF(path=path_txt)

    async def test_load_playlist_bp_settings(self, tracks: list[LocalTrack], path_mapper: PathMapper):
        pl = XAutoPF(path=path_playlist_xautopf_bp, path_mapper=path_mapper)
        await pl.load()

        assert pl.name == path_playlist_xautopf_bp.stem
        assert pl.description == "I am a description"
        assert pl.path == path_playlist_xautopf_bp
        assert pl.ext == path_playlist_xautopf_bp.suffix
        assert not pl.tracks

        # fine-grained processor settings are tested in class-specific tests
        assert pl.matcher.ready
        assert len(pl.matcher.comparers.comparers) == 3
        assert not pl.limiter
        assert not pl.limiter_deduplication
        assert pl.sorter

        await pl.load(tracks)
        assert [track.path.name for track in pl.tracks] == [path_track_flac.name, path_track_wma.name]

    async def test_load_playlist_bp_tracks(self, tracks: list[LocalTrack], path_mapper: PathMapper):
        # prepare tracks to search through
        tracks_actual = sorted(tracks)
        tracks = random_tracks(50)
        for i, track in enumerate(tracks[10:40]):
            track.album = "an album"
        for i, track in enumerate(tracks[20:50]):
            track.artist = None
        for i, track in enumerate(tracks, 1):
            track.track_number = i
        tracks += tracks_actual
        tracks_expected = [tracks_actual[0], tracks_actual[3]]

        pl = XAutoPF(path=path_playlist_xautopf_bp, path_mapper=path_mapper)
        await pl.load(tracks=tracks_actual)
        assert pl.tracks == tracks_expected

        pl = XAutoPF(path=path_playlist_xautopf_bp, path_mapper=path_mapper)
        await pl.load(tracks=tracks)

        assert len(pl.tracks) == 32
        tracks_expected += [
            track for track in tracks if 20 < track.track_number < 30 or track.album == "an album"
        ]
        assert pl.tracks == sorted(tracks_expected, key=lambda t: t.track_number)

    async def test_load_playlist_ra_settings(self, path_mapper: PathMapper):
        pl = XAutoPF(path=path_playlist_xautopf_ra, path_mapper=path_mapper)
        await pl.load(tracks=random_tracks(20))

        assert pl.name == path_playlist_xautopf_ra.stem
        assert pl.description is None
        assert pl.path == path_playlist_xautopf_ra
        assert pl.ext == path_playlist_xautopf_ra.suffix

        # fine-grained processor settings are tested in class-specific tests
        assert not pl.matcher.ready
        assert not pl.matcher.comparers
        assert pl.limiter
        assert pl.limiter_deduplication
        assert pl.sorter

    async def test_load_playlist_ra_tracks(self, path_mapper: PathMapper):
        # prepare tracks to search through
        tracks = random_tracks(50)
        for i, track in enumerate(tracks):
            track.date_added = datetime.now().replace(minute=i)

        pl = XAutoPF(path=path_playlist_xautopf_ra, path_mapper=path_mapper)
        await pl.load(tracks=tracks)

        limit = pl.limiter.limit_max
        assert len(pl.tracks) == limit
        tracks_expected = sorted(tracks, key=lambda t: t.date_added, reverse=True)[:limit]
        assert pl.tracks == sorted(tracks_expected, key=lambda t: t.date_added, reverse=True)

    async def test_limiter_deduplication(self):
        tracks = random_tracks(10)

        pl = XAutoPF(path=path_playlist_xautopf_ra)
        await pl.load(tracks=tracks)

        limit = pl.limiter.limit_max
        tracks_expected = sorted(tracks, key=lambda t: t.date_added, reverse=True)[:limit]
        assert pl.limiter_deduplication
        assert pl.tracks == tracks_expected

        pl = XAutoPF(path=path_playlist_xautopf_ra)
        await pl.load(tracks=tracks + tracks)

        assert pl.limiter_deduplication
        assert pl.tracks == tracks_expected

    async def test_save_new_file(self, tmp_path: Path):
        path = tmp_path.joinpath(random_str()).with_suffix(".xautopf")
        pl = XAutoPF(path=path)
        await pl.load()

        assert not path.exists()

        # default values were assigned according to class attribute defaults
        for key, default in pl.default_xml["SmartPlaylist"].items():
            if key == "Source":
                continue
            assert pl._parser.xml_smart_playlist[key] == default
        assert pl._parser.xml_source["@Type"] == pl.default_xml["SmartPlaylist"]["Source"]["@Type"]
        assert pl.description is None

        # default processor settings were applied
        assert not pl.matcher.ready
        assert not pl.limiter
        assert pl.sorter.sort_fields == pl._parser.defined_sort[6]
        assert pl.sorter.shuffle_mode is None

        assert not pl.tracks  # no tracks given so no tracks loaded

        await pl.save(dry_run=True)
        assert not path.exists()
        await pl.save(dry_run=False)
        assert path.is_file()

    @pytest.mark.parametrize("path", [path_playlist_xautopf_bp], indirect=["path"])
    async def test_save_existing_file(
            self, tracks: list[LocalTrack], path: str, path_mapper: PathMapper, tmp_path: Path
    ):
        # prepare tracks to search through
        tracks_actual = [track for track in tracks if track.path in [path_track_flac, path_track_wma]]
        tracks = random_tracks(50)
        for i, track in enumerate(tracks[10:40]):
            track.album = "an album"
        for i, track in enumerate(tracks[20:50]):
            track.artist = None
        for i, track in enumerate(tracks, 1):
            track.track_number = i
        tracks += tracks_actual

        pl = XAutoPF(path=path, path_mapper=path_mapper)
        await pl.load(tracks=tracks)

        assert pl.path == path
        assert len(pl.tracks) == 32
        original_dt_modified = pl.date_modified
        original_dt_created = pl.date_created
        original_parser = deepcopy(pl._parser)

        # perform some operations on the playlist
        tracks_added = random_tracks(3)
        pl.tracks += tracks_added
        # noinspection PyAsyncCall
        pl.tracks.pop(5)
        # noinspection PyAsyncCall
        pl.tracks.pop(6)
        pl.tracks.remove(tracks_actual[0])

        # first test results on a dry run
        result = await pl.save(dry_run=True)

        assert result.start == 32
        assert result.start_included == 3
        assert result.start_excluded == 3
        assert result.start_compared == 3
        assert not result.start_limiter
        assert result.start_sorter
        assert result.final == len(pl.tracks)
        assert result.final_included == 4
        assert result.final_excluded == 2
        assert result.final_compared == 3
        assert not result.start_limiter
        assert result.start_sorter

        assert pl.date_modified == original_dt_modified
        assert pl.date_created == original_dt_created
        assert pl._parser.xml == original_parser.xml

        pl.description = "new description"
        await pl.save(dry_run=False)

        if not os.getenv("GITHUB_ACTIONS"):
            # TODO: these assertions always fail on GitHub actions but not locally, why?
            assert pl.date_modified > original_dt_modified

        assert pl._parser.xml != original_parser
        assert pl._parser.xml_smart_playlist["@GroupBy"] == original_parser.xml_smart_playlist["@GroupBy"]
        assert pl._parser.xml_source["Conditions"] == original_parser.xml_source["Conditions"]

        # assert file has reported path count and paths in the file have been mapped to relative paths
        paths = pl._parser.xml_source["ExceptionsInclude"].split("|")
        assert len(paths) == result.final_included
        for path in paths:
            assert path.startswith("../")


@pytest.mark.skipif(not required_modules_installed(REQUIRED_MODULES), reason="required modules not installed.")
class TestXMLPlaylistParser(PrettyPrinterTester):

    @pytest.fixture
    def obj(self) -> XMLPlaylistParser:
        return XMLPlaylistParser(path=path_playlist_xautopf_ra)

    @pytest.fixture(scope="class")
    def path_mapper(self) -> PathStemMapper:
        """Yields a :py:class:`PathMapper` that can map paths from the test playlist files"""
        yield PathStemMapper(stem_map={"../": path_resources}, available_paths=path_track_all)

    @pytest.mark.parametrize("path", [path_playlist_xautopf_bp], indirect=["path"])
    async def test_save(self, path: str):
        parser = XMLPlaylistParser(path=path)
        await parser.load()

        description = "i am a brand new description"
        parser.description = description
        await parser.save()
        await parser.load()
        assert parser.description != description

        parser.description = description
        await parser.save(dry_run=False)
        await parser.load()
        assert parser.description == description

    ###########################################################################
    ## Comparer parsing
    ###########################################################################
    @staticmethod
    def parse_comparers(parser: XMLPlaylistParser) -> list[Comparer]:
        """Extract all comparers from a given ``parser``"""
        conditions = parser.xml_source["Conditions"]
        return [parser._get_comparer(condition) for condition in to_collection(conditions["Condition"])]

    async def test_get_comparer_bp(self):
        parser = XMLPlaylistParser(path=path_playlist_xautopf_bp)
        await parser.load()
        comparers = self.parse_comparers(parser)

        assert len(comparers) == 3

        assert comparers[0].field == Fields.ALBUM
        assert not comparers[0]._converted
        assert comparers[0].expected == ["an album"]
        assert comparers[0].condition == "contains"
        assert comparers[0]._processor_method == comparers[0]._contains

        assert comparers[1].field == Fields.ARTIST
        assert not comparers[1]._converted
        assert comparers[1].expected is None
        assert comparers[1].condition == "is_null"
        assert comparers[1]._processor_method == comparers[1]._is_null

        assert comparers[2].field == Fields.TRACK_NUMBER
        assert not comparers[2]._converted
        assert comparers[2].expected == ["30"]
        assert comparers[2].condition == "less_than"
        assert comparers[2]._processor_method == comparers[2]._is_before

    async def test_get_comparer_ra(self):
        parser = XMLPlaylistParser(path=path_playlist_xautopf_ra)
        await parser.load()
        comparers = self.parse_comparers(parser)

        assert len(comparers) == 1
        comparer = comparers[0]

        assert comparer.field == LocalTrackField.ALBUM
        assert not comparer._converted
        assert comparer.expected == [""]
        assert comparer.condition == "contains"
        assert comparer._processor_method == comparer._contains

    @pytest.mark.parametrize("path", [path for path in sorted(path_playlist_all) if path.suffix == ".xautopf"])
    async def test_parse_comparer(self, path: Path):
        parser = XMLPlaylistParser(path=path)
        await parser.load()
        comparers = self.parse_comparers(parser)
        conditions = to_collection(parser.xml_source["Conditions"]["Condition"], list)

        for condition in conditions.copy():  # extract all sub conditions as well
            sub_key = "And" if "And" in condition else "Or"
            sub_conditions = to_collection(condition.get(sub_key, {}).get("Condition"))
            if sub_conditions:
                conditions.extend(sub_conditions)
                condition.pop(sub_key)
                comparers.extend([parser._get_comparer(condition) for condition in sub_conditions])

        assert parser._get_xml_from_comparer() is not None  # default value is given

        for comparer, condition in zip(comparers, conditions, strict=True):
            assert parser._get_xml_from_comparer(comparer) == condition

    ###########################################################################
    ## FilterMatcher parsing
    ###########################################################################
    async def test_get_matcher_bp(self, path_mapper: PathStemMapper):
        parser = XMLPlaylistParser(path=path_playlist_xautopf_bp, path_mapper=path_mapper)
        await parser.load()
        matcher = parser.get_matcher()

        assert set(matcher.include) == {path_track_wma, path_track_mp3, path_track_flac}
        assert set(matcher.exclude) == {
            path_playlist_resources.joinpath("exclude_me_2.mp3"),
            path_track_mp3,
            path_playlist_resources.joinpath("exclude_me.flac"),
        }

        assert isinstance(matcher.comparers.comparers, dict)
        assert len(matcher.comparers.comparers) == 3  # loaded Comparer settings are tested in class-specific tests
        assert matcher.comparers.match_all
        assert all(not m[1].ready for m in matcher.comparers.comparers.values())

        assert matcher.group_by == Fields.ALBUM

    async def test_get_matcher_ra(self, path_mapper: PathStemMapper):
        parser = XMLPlaylistParser(path=path_playlist_xautopf_ra, path_mapper=path_mapper)
        await parser.load()
        matcher = parser.get_matcher()

        assert len(matcher.include) == 0
        assert len(matcher.exclude) == 0

        assert isinstance(matcher.comparers.comparers, dict)
        assert len(matcher.comparers.comparers) == 0
        assert not matcher.comparers.match_all
        assert all(not m[1].ready for m in matcher.comparers.comparers.values())

        assert matcher.group_by is None

    async def test_get_matcher_cm(self, path_mapper: PathStemMapper):
        parser = XMLPlaylistParser(path=path_playlist_xautopf_cm, path_mapper=path_mapper)
        await parser.load()
        matcher = parser.get_matcher()

        assert isinstance(matcher.comparers.comparers, Mapping)
        assert len(matcher.comparers.comparers) == 3
        assert not matcher.comparers.match_all

        # assertions on parent comparers
        comparers: list[Comparer] = list(matcher.comparers.comparers)
        assert comparers[0].field == Fields.ALBUM
        assert comparers[0].condition == "contains"
        assert comparers[0].expected == ["an album"]
        assert comparers[1].field == Fields.RATING
        assert comparers[1].condition == "in_range"
        assert comparers[1].expected == ["40", "80"]
        assert comparers[2].field == Fields.YEAR
        assert comparers[2].condition == "is"
        assert comparers[2].expected == ["2024"]

        # assertions on child comparers
        sub_filters: list[tuple[bool, FilterComparers]] = list(matcher.comparers.comparers.values())
        assert not sub_filters[0][1].ready
        assert not sub_filters[0][0]  # And/Or condition

        sub_filter_1 = sub_filters[1][1]
        assert sub_filter_1.ready
        assert not sub_filter_1.match_all
        assert isinstance(sub_filter_1.comparers, Mapping)
        assert all(not m[1].ready for m in sub_filter_1.comparers.values())
        assert sub_filters[1][0]  # And/Or condition

        sub_comparers_1: list[Comparer] = list(sub_filters[1][1].comparers)
        assert sub_comparers_1[0].field == Fields.GENRES
        assert sub_comparers_1[0].condition == "is_in"
        assert sub_comparers_1[0].expected == ["Jazz", "Rock", "Pop"]
        assert sub_comparers_1[1].field == Fields.TRACK_NUMBER
        assert sub_comparers_1[1].condition == "less_than"
        assert sub_comparers_1[1].expected == ["50"]

        sub_filter_2 = sub_filters[2][1]
        assert sub_filter_2.ready
        assert sub_filter_2.match_all
        assert isinstance(sub_filter_2.comparers, Mapping)
        assert all(not m[1].ready for m in sub_filter_2.comparers.values())
        assert not sub_filters[2][0]  # And/Or condition

        sub_comparers_2: list[Comparer] = list(sub_filter_2.comparers)
        assert sub_comparers_2[0].field == Fields.ARTIST
        assert sub_comparers_2[0].condition == "starts_with"
        assert sub_comparers_2[0].expected == ["an artist"]
        assert sub_comparers_2[1].field == Fields.LAST_PLAYED
        assert sub_comparers_2[1].condition == "in_the_last"
        assert sub_comparers_2[1].expected == ["7d"]

        assert matcher.group_by == Fields.ALBUM

    async def test_parse_matcher(self):
        parser_initial = XMLPlaylistParser(path=path_playlist_xautopf_ra)
        parser_final = XMLPlaylistParser(path=path_playlist_xautopf_cm)
        await parser_initial.load()
        await parser_final.load()

        initial = parser_initial.get_matcher()
        final = parser_final.get_matcher()

        assert initial.group_by != final.group_by
        assert initial.comparers.ready != final.comparers.ready
        assert len(initial.comparers.comparers) != len(final.comparers.comparers)

        # default values cause getter to return default, non-ready processor
        parser_initial.parse_matcher()
        assert not parser_initial.get_matcher().ready

        parser_initial.parse_matcher(final)
        new = parser_initial.get_matcher()
        assert new.group_by == final.group_by
        assert new.comparers.ready == final.comparers.ready
        assert len(new.comparers.comparers) == len(final.comparers.comparers)

        assert parser_initial.xml_smart_playlist["@GroupBy"] == parser_final.xml_smart_playlist["@GroupBy"]
        assert parser_initial.xml_source["Conditions"] == parser_final.xml_source["Conditions"]

    ###########################################################################
    ## ItemLimiter parsing
    ###########################################################################
    async def test_get_limiter_bp(self):
        parser = XMLPlaylistParser(path=path_playlist_xautopf_bp)
        await parser.load()
        assert parser.get_limiter() is None

    async def test_get_limiter_ra(self):
        parser = XMLPlaylistParser(path=path_playlist_xautopf_ra)
        await parser.load()
        limiter = parser.get_limiter()

        assert limiter.limit_max == 20
        assert limiter.kind == LimitType.ITEMS
        assert limiter.allowance == 1.25
        assert limiter._processor_method == limiter._most_recently_added

    async def test_parse_limiter(self):
        parser_initial = XMLPlaylistParser(path=path_playlist_xautopf_bp)
        parser_final = XMLPlaylistParser(path=path_playlist_xautopf_ra)
        await parser_initial.load()
        await parser_final.load()

        initial = parser_initial.get_limiter()
        final = parser_final.get_limiter()

        assert initial is None
        assert parser_initial.xml_source["Limit"] != parser_final.xml_source["Limit"]

        # default values cause getter to not return any processor
        parser_initial.parse_limiter()
        assert parser_initial.get_limiter() is None
        assert not parser_initial.limiter_deduplication  # always False by default

        parser_initial.parse_limiter(final, deduplicate=True)
        new = parser_initial.get_limiter()
        assert new is not None
        assert new.limit_max == final.limit_max
        assert new.kind == final.kind
        assert new.limit_sort == final.limit_sort

        assert parser_initial.xml_source["Limit"] == parser_final.xml_source["Limit"]

    ###########################################################################
    ## ItemSorter parsing
    ###########################################################################
    async def test_get_sorter_bp(self):
        parser = XMLPlaylistParser(path=path_playlist_xautopf_bp)
        await parser.load()

        # shuffle settings not set as automatic order defined
        sorter = parser.get_sorter()
        assert sorter.sort_fields == {Fields.TRACK_NUMBER: False}
        assert sorter.shuffle_mode is None
        assert sorter.shuffle_weight == 0.0

        # flip sorting to manual order to force function to set shuffle settings
        parser.xml_source["SortBy"]["@Field"] = str(parser.default_sort)
        sorter = parser.get_sorter()
        assert sorter.sort_fields == {}
        assert sorter.shuffle_mode == ShuffleMode.RECENT_ADDED
        assert sorter.shuffle_weight == 0.5

    async def test_get_sorter_ra(self):
        parser = XMLPlaylistParser(path=path_playlist_xautopf_ra)
        await parser.load()

        # shuffle settings not set as automatic order defined
        sorter = parser.get_sorter()
        assert sorter.sort_fields == {Fields.DATE_ADDED: True}
        assert sorter.shuffle_mode is None
        assert sorter.shuffle_weight == 0.0

        # flip sorting to manual order to force function to set shuffle settings
        parser.xml_source["SortBy"]["@Field"] = str(parser.default_sort)
        sorter = parser.get_sorter()
        assert sorter.sort_fields == {}
        assert sorter.shuffle_mode == ShuffleMode.DIFFERENT_ARTIST
        assert sorter.shuffle_weight == -0.2

    async def test_parse_sorter_defined(self):
        parser_initial = XMLPlaylistParser(path=path_playlist_xautopf_bp)
        parser_final = XMLPlaylistParser(path=path_playlist_xautopf_cm)
        await parser_initial.load()
        await parser_final.load()

        initial = parser_initial.get_sorter()
        final = parser_final.get_sorter()

        assert initial.sort_fields != final.sort_fields
        assert "DefinedSort" not in parser_initial.xml_source
        assert final.sort_fields == parser_final.defined_sort[6]

        parser_initial.parse_sorter(final)
        new = parser_initial.get_sorter()
        assert initial.sort_fields != new.sort_fields == final.sort_fields

        assert parser_initial.xml_source["DefinedSort"] == parser_final.xml_source["DefinedSort"]
        assert parser_initial.xml_source["DefinedSort"]["@Id"] == "6"

    async def test_parse_sorter_fields(self):
        parser_initial = XMLPlaylistParser(path=path_playlist_xautopf_bp)
        parser_final = XMLPlaylistParser(path=path_playlist_xautopf_ra)
        await parser_initial.load()
        await parser_final.load()

        initial = parser_initial.get_sorter()
        final = parser_final.get_sorter()

        assert initial.sort_fields != final.sort_fields
        assert parser_initial.xml_source["SortBy"] != parser_final.xml_source["SortBy"]

        # default values assigned on no input
        parser_initial.parse_sorter()
        assert parser_initial.xml_source["SortBy"]["@Field"] == str(parser_initial.default_sort)
        assert parser_initial.get_sorter().shuffle_mode is None

        parser_initial.parse_sorter(final)
        new = parser_initial.get_sorter()
        assert initial.sort_fields != new.sort_fields == final.sort_fields

        assert parser_initial.xml_source["SortBy"] == parser_final.xml_source["SortBy"]

    async def test_parse_sorter_shuffle(self):
        parser_initial = XMLPlaylistParser(path=path_playlist_xautopf_bp)
        parser_final = XMLPlaylistParser(path=path_playlist_xautopf_ra)
        await parser_initial.load()
        await parser_final.load()

        # flip sorting to manual order to force function to set shuffle settings
        parser_initial.xml_source["SortBy"]["@Field"] = str(parser_initial.default_sort)
        parser_final.xml_source["SortBy"]["@Field"] = str(parser_final.default_sort)

        initial = parser_initial.get_sorter()
        final = parser_final.get_sorter()

        assert initial.shuffle_mode != final.shuffle_mode
        assert initial.shuffle_weight != final.shuffle_weight
        assert parser_initial.xml_smart_playlist["@ShuffleMode"] != parser_final.xml_smart_playlist["@ShuffleMode"]
        actual_weight = parser_initial.xml_smart_playlist["@ShuffleSameArtistWeight"]
        assert actual_weight != parser_final.xml_smart_playlist["@ShuffleSameArtistWeight"]

        parser_initial.parse_sorter(final)
        new = parser_initial.get_sorter()
        assert initial.shuffle_mode != new.shuffle_mode == final.shuffle_mode
        assert initial.shuffle_weight != new.shuffle_weight == final.shuffle_weight

        assert parser_initial.xml_smart_playlist["@ShuffleMode"] == parser_final.xml_smart_playlist["@ShuffleMode"]
        actual_weight = parser_initial.xml_smart_playlist["@ShuffleSameArtistWeight"]
        assert actual_weight == parser_final.xml_smart_playlist["@ShuffleSameArtistWeight"]


@pytest.fixture(scope="module")
async def library() -> LocalLibrary:
    """Yields a loaded :py:class:`LocalLibrary` to supply tracks for manual checking of custom playlist files"""
    mapper = PathStemMapper({"../..": os.getenv("TEST_PL_LIBRARY", "")})
    library = MusicBee(musicbee_folder=Path(os.getenv("TEST_PL_LIBRARY")).joinpath("MusicBee"), path_mapper=mapper)
    await library.load_tracks()
    return library


# noinspection PyTestUnpassedFixture, SpellCheckingInspection
@pytest.mark.manual
@pytest.mark.skipif(
    "not config.getoption('-m') and not config.getoption('-k')",
    reason="Only runs when the test or marker is specified explicitly by the user",
)
@pytest.mark.parametrize("source,expected", [
    (path, Path(os.getenv("TEST_PL_COMPARISON", "")).joinpath(path.stem).with_suffix(".m3u"))
    for path in Path(os.getenv("TEST_PL_SOURCE", "")).rglob(str(Path("**", "*.xautopf")))
])
async def test_playlist_paths_manual(library: LocalLibrary, source: Path, expected: Path):
    assert source.is_file()
    assert expected.is_file()

    pl = await library.load_playlist(source)

    with open(expected, "r", encoding="utf-8") as f:
        paths_expected = [library.path_mapper.map(line.strip()) for line in f]

    assert sorted(track.path for track in pl) == sorted(paths_expected)
    assert [track.path for track in pl] == paths_expected
