from copy import deepcopy
from datetime import datetime
from pathlib import Path
from random import choice
from unittest.mock import patch

import pytest
from faker import Faker
from pydantic import TypeAdapter
from pydantic.alias_generators import to_pascal
from pytest_mock import MockerFixture, mocker

# noinspection PyProtectedMember
from musify.local.collection.playlist.xautopf import REQUIRED_MODULES, XAutoPF, _XMLCondition, _XMLConditions, \
    _XMLLimit, _XMLDisplayField, _XMLDisplayGroup, _XMLSortBy, _XMLDefinedSort, _XMLSource, _XMLSmartPlaylist, \
    _XMLRoot, _XMLDisplayFields, SyncXAutoPFResult, AutoMatcher
from musify.local.item.track import LocalTrack
from musify.models.item.track import Track
from musify.models.properties.file import PathMapper
from musify.processors_new.compare import Comparer
from musify.processors_new.filters import ComparerFilter, PathsFilter, MatchFilter
from musify.processors_new.limit import LimitType, ItemLimiter
from musify.processors_new.sort import ShuffleMode, ItemSorter, SORT_FIELDS
from musify.utils import required_modules_installed
from tests.local.collection.playlist.testers import LocalPlaylistTester
from tests.models.testers import BaseModelTester


class TestSyncXAutoPFResult(BaseModelTester):
    @pytest.fixture
    def model(self, faker: Faker) -> SyncXAutoPFResult:
        return SyncXAutoPFResult(
            start=faker.random_int(0, 100),
            start_included=faker.random_int(0, 100),
            start_excluded=faker.random_int(0, 100),
            start_compared=faker.random_int(0, 100),
            start_limit=faker.random_int(0, 100),
            start_sort=faker.boolean(),
            final=faker.random_int(0, 100),
            final_included=faker.random_int(0, 100),
            final_excluded=faker.random_int(0, 100),
            final_compared=faker.random_int(0, 100),
            final_limit=faker.random_int(0, 100),
            final_sort=faker.boolean(),
        )

    def test_from_xml(self, tracks: list[LocalTrack], xml_playlist_recent: str, faker: Faker):
        for track in tracks:
            track.added_at = datetime(2024, 1, faker.random_int(1, 28))
            track.last_played_at = datetime(2024, 3, faker.random_int(1, 28))

        initial_xml = _XMLRoot.model_validate(xml_playlist_recent)
        final_xml = deepcopy(initial_xml)

        initial_matcher = AutoMatcher(
            compare=ComparerFilter(
                comparers=Comparer(field="path", condition="IsIn", expected={tr.path for tr in tracks[:20]})
            ),
            include=PathsFilter(values=tracks[10:25]),
            exclude=PathsFilter(values=tracks[18:22]),
        )
        initial_xml.smart_playlist.parse_matcher(initial_matcher)

        final_matcher = deepcopy(initial_matcher)
        final_matcher.include = PathsFilter(values=tracks[10:13])
        final_matcher.exclude = PathsFilter(values=tracks[18:20])
        final_xml.smart_playlist.parse_matcher(final_matcher)

        limiter = final_xml.smart_playlist.source.limit
        limiter.count -= 5

        initial_tracks = tracks[5:29]
        final_tracks = tracks[:12] + tracks[23:27]

        result = SyncXAutoPFResult.from_xml(initial_tracks, initial_xml, final_tracks, final_xml)
        assert result == SyncXAutoPFResult(
            start=len(initial_tracks),
            start_included=len(initial_matcher.include.values),
            start_excluded=len(initial_matcher.exclude.values),
            start_compared=15,
            start_limit=20,
            start_sort=True,
            final=len(final_tracks),
            final_included=len(final_matcher.include.values),
            final_excluded=len(final_matcher.exclude.values),
            final_compared=12,
            final_limit=15,
            final_sort=True,
        )


@pytest.fixture
def xml_playlist_basic() -> str:
    """A basic XAutoPF playlist XML structure for testing purposes."""
    # noinspection PyPep8
    return """
<?xml version="1.0" encoding="utf-8"?>
<SmartPlaylist SaveStaticCopy="true" LiveUpdating="true" Layout="0" LayoutGroupBy="0" ShuffleMode="RecentAdded" ShuffleSameArtistWeight="0.5" GroupBy="album" ConsolidateAlbums="false" MusicLibraryPath="/mnt/d/Music/">
  <Source Type="1">
    <Description>I am a description</Description>
    <Conditions CombineMethod="All">
      <Condition Field="Album" Comparison="Contains" Value="an album" />
      <Condition Field="ArtistPeople" Comparison="IsNull" />
      <Condition Field="TrackNo" Comparison="LessThan" Value="30" />
    </Conditions>
    <Limit FilterDuplicates="false" Enabled="false" Count="25" Type="Minutes" SelectedBy="MostRecentlyAdded" />
    <SortBy Field="86" Order="Ascending" />
    <Fields>
      <Group Id="TrackDetail">
        <Field Code="20" Width="24" />
        <Field Code="78" Width="48" />
        <Field Code="65" Width="769" />
        <Field Code="16" Width="121" />
        <Field Code="32" Width="534" />
        <Field Code="30" Width="531" />
        <Field Code="12" Width="354" />
        <Field Code="14" Width="97" />
      </Group>
    </Fields>
    <ExceptionsInclude>../track/NOISE_FLaC.flac|../track/noiSE_mP3.mp3|../track/noise_wma.wma</ExceptionsInclude>
    <Exceptions>../playlist/exclude_me.flac|../playlist/exclude_me_2.mp3|../track/noiSE_mP3.mp3</Exceptions>
  </Source>
</SmartPlaylist>
    """.strip()


@pytest.fixture
def xml_playlist_complex() -> str:
    """A complex XAutoPF playlist XML structure for testing purposes."""
    # noinspection PyPep8
    return """
<?xml version="1.0" encoding="utf-8"?>
<SmartPlaylist SaveStaticCopy="true" LiveUpdating="true" Layout="0" LayoutGroupBy="0" ShuffleMode="RecentAdded" ShuffleSameArtistWeight="0.5" GroupBy="album" ConsolidateAlbums="false" MusicLibraryPath="/mnt/d/Music/">
  <Source Type="1">
    <Description>This has got some complex matching</Description>
    <Conditions CombineMethod="Any">
      <Condition Field="Album" Comparison="Contains" Value="an album" />
      <Condition Field="Rating" Comparison="InRange" Value1="40" Value2="80">
        <And CombineMethod="Any">
          <Condition Field="FolderName" Comparison="IsIn" Value1="Jazz" Value2="Rock" Value3="Pop" />
          <Condition Field="TrackNo" Comparison="LessThan" Value="50" />
        </And>
      </Condition>
      <Condition Field="Rating" Comparison="Is" Value="5">
        <Or CombineMethod="All">
          <Condition Field="Title" Comparison="StartsWith" Value="a title" />
          <Condition Field="FileLastPlayed" Comparison="InTheLast" Value="7d" />
        </Or>
      </Condition>
    </Conditions>
    <Limit FilterDuplicates="false" Enabled="true" Count="1" Type="Seconds" SelectedBy="MostRecentlyAdded" />
    <DefinedSort Id="6" />
    <Fields>
      <Group Id="TrackDetail">
        <Field Code="20" Width="24" />
        <Field Code="78" Width="48" />
        <Field Code="65" Width="769" />
        <Field Code="16" Width="121" />
        <Field Code="32" Width="534" />
        <Field Code="30" Width="531" />
        <Field Code="12" Width="354" />
        <Field Code="14" Width="97" />
      </Group>
    </Fields>
    <ExceptionsInclude>../track/include_me.flac|../track/include_me.mp3</ExceptionsInclude>
    <Exceptions>../track/ignore_me.flac|../track/ignore_me.mp3</Exceptions>
  </Source>
</SmartPlaylist>
    """.strip()


# TODO: find a way to add back empty Description, Exceptions, ExceptionsInclude fields
@pytest.fixture
def xml_playlist_recent() -> str:
    """A recently added tracks XAutoPF playlist XML structure for testing purposes."""
    # noinspection PyPep8
    return """
<?xml version="1.0" encoding="utf-8"?>
<SmartPlaylist SaveStaticCopy="false" LiveUpdating="true" Layout="4" LayoutGroupBy="0" ShuffleMode="DifferentArtist" ShuffleSameArtistWeight="-0.2" GroupBy="track" ConsolidateAlbums="false" MusicLibraryPath="/mnt/d/Music/">
  <Source Type="1">
    <Conditions CombineMethod="Any">
      <Condition Field="Album" Comparison="Contains" Value="" />
    </Conditions>
    <Limit FilterDuplicates="true" Enabled="true" Count="20" Type="Items" SelectedBy="MostRecentlyAdded" />
    <SortBy Field="12" Order="Descending" />
    <Fields>
      <Group Id="TrackDetail">
        <Field Code="20" Width="24" />
        <Field Code="78" Width="48" />
        <Field Code="65" Width="751" />
        <Field Code="16" Width="117" />
        <Field Code="32" Width="562" />
        <Field Code="30" Width="517" />
        <Field Code="12" Width="336" />
        <Field Code="14" Width="128" />
      </Group>
      <Group Id="Album">
        <Field Code="78" Width="25" />
        <Field Code="31" Width="135" />
        <Field Code="65" Width="160" />
        <Field Code="30" Width="110" />
        <Field Code="59" Width="130" />
        <Field Code="75" Width="75" />
        <Field Code="16" Width="34" />
        <Field Code="12" Width="75" />
      </Group>
    </Fields>
  </Source>
</SmartPlaylist>
    """.strip()


# noinspection PyUnresolvedReferences
@pytest.fixture(params=[
    pytest.lazy_fixture("xml_playlist_basic"),
    pytest.lazy_fixture("xml_playlist_complex"),
    pytest.lazy_fixture("xml_playlist_recent"),
])
def xml_playlist(request) -> str:
    """Yields different XAutoPF playlist XML structures for testing purposes."""
    return request.param


class TestXAutoPF(LocalPlaylistTester):

    @pytest.fixture
    async def model(self, path_mapper: PathMapper, faker: Faker, tmp_path: Path) -> XAutoPF:
        path = tmp_path.joinpath(faker.file_path(absolute=False, extension="xautopf"))
        playlist = XAutoPF(path=path, path_mapper=path_mapper)
        return await playlist.load()

    @pytest.fixture
    async def model_with_tracks(
            self, model: XAutoPF, tracks: list[LocalTrack], tracks_summed: list[LocalTrack]
    ) -> XAutoPF:
        """A model with tracks already loaded for testing purposes."""
        model._original[:] = tracks
        model.tracks[:] = tracks_summed
        return model

    @pytest.fixture
    def tracks(self, tracks: list[LocalTrack], faker: Faker) -> list[LocalTrack]:
        """A list of tracks with varied added_at and last_played_at dates."""
        for track in tracks:
            track.added_at = datetime(2024, 1, faker.random_int(1, 28))
            track.last_played_at = datetime(2024, 3, faker.random_int(1, 28))

        return tracks

    @pytest.fixture
    def tracks_compared(self, model: XAutoPF, tracks: list[LocalTrack]) -> list[LocalTrack]:
        """Tracks to be included in the playlist via comparers."""
        return tracks[:20]

    @pytest.fixture
    def tracks_included(self, model: XAutoPF, tracks: list[LocalTrack]) -> list[LocalTrack]:
        """Tracks to be included in the playlist."""
        return tracks[10:25]

    @pytest.fixture
    def tracks_excluded(self, model: XAutoPF, tracks: list[LocalTrack]) -> list[LocalTrack]:
        """Tracks to be excluded in the playlist."""
        return tracks[18:22]

    @pytest.fixture
    def tracks_summed(self, tracks: list[LocalTrack]) -> list[LocalTrack]:
        return tracks[:18] + tracks[22:25]

    @pytest.fixture
    def matcher(
            self,
            tracks_compared: list[LocalTrack],
            tracks_included: list[LocalTrack],
            tracks_excluded: list[LocalTrack],
            path_mapper: PathMapper
    ) -> MatchFilter:
        return MatchFilter(
            compare=ComparerFilter(
                comparers=Comparer(field="path", condition="IsIn", expected={tr.path for tr in tracks_compared})
            ),
            include=PathsFilter(values=tracks_included, path_mapper=path_mapper),
            exclude=PathsFilter(values=tracks_excluded, path_mapper=path_mapper),
        )

    @pytest.fixture
    def path(self, model: XAutoPF, xml_playlist_recent: str) -> Path:
        """Creates an actual playlist file."""
        model.path.parent.mkdir(parents=True, exist_ok=True)
        model.path.write_text(xml_playlist_recent, encoding="utf-8")
        return model.path

    async def test_limiter_deduplication(
            self,
            model: XAutoPF,
            path: Path,
            tracks: list[LocalTrack],
            path_mapper: PathMapper,
            faker: Faker
    ):
        await model.load()
        assert not model.tracks
        assert model.limiter_deduplication

        limit = model.limiter.limit_by
        tracks_expected = sorted(tracks, key=lambda t: t.added_at, reverse=True)[:limit]

        await model.load(tracks)
        assert model.tracks == tracks_expected

        # add duplicates and apply deduplication
        await model.load(tracks=tracks + tracks)
        assert model.tracks == tracks_expected

    @staticmethod
    async def assert_load(model: XAutoPF, xml: _XMLRoot, tracks: list[LocalTrack], mocker: MockerFixture) -> None:
        """Asserts loading of a playlist from a given path with expected XML structure and tracks."""
        assert model._xml is None
        assert not model.tracks
        assert not model.description
        assert not model.matcher
        assert not model.limiter
        assert not model.sorter

        await model.load()
        assert model._xml == xml
        assert not model.tracks
        assert model.description == xml.smart_playlist.source.description

        matcher = xml.smart_playlist.matcher
        matcher.include.path_mapper = model.path_mapper
        matcher.exclude.path_mapper = model.path_mapper
        assert model.matcher == matcher
        assert model.limiter == xml.smart_playlist.source.limit.limiter
        assert model.sorter == xml.smart_playlist.sorter

        mock_match = mocker.spy(model, "_match_tracks")
        mock_limit = mocker.spy(model, "_limit_tracks")
        mock_sort = mocker.spy(model, "_sort_tracks")

        reference = model._get_reference_for_last_played_track(tracks.copy())
        await model.load(tracks)

        mock_match.assert_called_once_with(tracks=tracks, reference=reference)
        mock_limit.assert_called_once_with(ignore=model.matcher.exclude.values)
        mock_sort.assert_called_once_with()

    async def test_load_from_no_file(self, model: XAutoPF, tracks: list[LocalTrack], mocker: MockerFixture):
        model = XAutoPF(path=model.path, path_mapper=model.path_mapper)
        await self.assert_load(model, _XMLRoot(), tracks, mocker=mocker)

    async def test_load_from_file(
            self, model: XAutoPF, xml_playlist: str, tracks: list[LocalTrack], mocker: MockerFixture
    ):
        model.path.parent.mkdir(parents=True, exist_ok=True)
        model.path.write_text(xml_playlist, encoding="utf-8")

        model = XAutoPF(path=model.path, path_mapper=model.path_mapper)
        xml = _XMLRoot.model_validate(xml_playlist)
        await self.assert_load(model, xml, tracks, mocker=mocker)

    def test_clean_matcher_paths_filters_paths(
            self, model_with_tracks: XAutoPF, matcher: MatchFilter, tracks: list[LocalTrack],
    ):
        assert matcher.compare.ready
        model_with_tracks.matcher = matcher

        model_with_tracks._clean_matcher_paths()
        # drops paths already in compared and excluded paths not in compared
        assert matcher.include.paths == {tr.path for tr in tracks[22:25]}
        # drops paths not in compared or included
        assert matcher.exclude.paths == {tr.path for tr in tracks[18:20]}

    def test_clean_matcher_paths_sets_paths(self, model_with_tracks: XAutoPF, matcher: MatchFilter):
        matcher.compare = ComparerFilter()
        model_with_tracks.matcher = matcher

        model_with_tracks._clean_matcher_paths()
        assert matcher.include.paths == {tr.path for tr in model_with_tracks.tracks}
        assert not matcher.exclude.paths

    def assert_saved_file(self, model: XAutoPF) -> None:
        """Asserts that the saved playlist file contains the correct mapped paths."""
        with model.path.open("r") as file:  # changed file
            assert file.read() == model._xml.unparse_xml()

        # assert file has reported path count and paths in the file have been mapped to relative paths
        paths = model._xml.smart_playlist.source.exceptions or set()
        paths |= model._xml.smart_playlist.source.exceptions_include or set()
        self.assert_paths_are_mapped(paths)

    async def test_save_file_dry_run(
            self, model_with_tracks: XAutoPF, tracks: list[LocalTrack], xml_playlist_complex: str
    ):
        model_with_tracks._xml = _XMLRoot.model_validate(xml_playlist_complex)
        await model_with_tracks.load()
        await self.assert_save_dry_run(model_with_tracks)

    async def test_save_to_new_file(
            self, model_with_tracks: XAutoPF, matcher: MatchFilter, xml_playlist_complex: str
    ):
        model_with_tracks._xml = _XMLRoot.model_validate(xml_playlist_complex)
        await model_with_tracks.load()
        model_with_tracks.matcher = matcher

        await self.assert_save(model_with_tracks)
        self.assert_saved_file(model_with_tracks)

    async def test_save_to_existing_file(
            self, model_with_tracks: XAutoPF, path: Path, matcher: MatchFilter
    ):
        await model_with_tracks.load()
        model_with_tracks.matcher = matcher

        original_xml = deepcopy(model_with_tracks._xml)
        await self.assert_save_to_existing_file(model_with_tracks)
        assert model_with_tracks._xml != original_xml
        self.assert_saved_file(model_with_tracks)

    async def test_save_to_new_file_from_existing(self, model_with_tracks: XAutoPF, path: Path):
        await model_with_tracks.load()
        await self.assert_save_to_new_file(model_with_tracks, path)


class TestXMLCondition(BaseModelTester):

    @pytest.fixture
    def model(self) -> _XMLCondition:
        return _XMLCondition()

    def test_all_fields_have_codes(self):
        assert not set(_XMLCondition.name_field_map) - set(_XMLCondition.name_code_map)

    def test_reference_required(self, model: _XMLCondition):
        assert model.reference_values

        model.value = [choice(list(model.reference_values))]
        assert model.reference_required

        model.value = ["not a reference value"]
        assert not model.reference_required

    def test_merge_values(self, adapter: TypeAdapter[_XMLCondition]):
        model = adapter.validate_python({"@Value": "a"})
        assert model.value == ["a"]

        model = adapter.validate_python(
            {"@Value1": "a", "@Value2": "b", "@Value3": "c", "@Value4": "d"}
        )
        assert model.value == ["a", "b", "c", "d"]

        model.value = ["1", "2", "3"]
        assert model.value == ["1", "2", "3"]

    def test_validate_field_is_mapped(self, model: _XMLCondition):
        with pytest.raises(ValueError):
            model.field = "NotAField"

        model.field = choice(tuple(model.name_field_map))

    def test_validate_only_and_either_or_set(self, model: _XMLCondition):
        assert model.And is None and model.Or is None
        model.And = _XMLConditions()
        with pytest.raises(ValueError):
            model.Or = _XMLConditions()

        model.And = None
        model.Or = _XMLConditions()
        with pytest.raises(ValueError):
            model.And = _XMLConditions()

    def test_build_comparer(self, model: _XMLCondition):
        model.field = "TrackNo"
        model.comparison = "IsIn"
        model.value = ["a", "b", "c"]

        comparer = model.comparer
        assert comparer == Comparer(
            field="track.number",
            condition="IsIn",
            expected=["a", "b", "c"],
            reference_required=model.reference_required,
        )

    def test_parse_comparer(self, adapter: TypeAdapter[_XMLCondition]):
        comparer = Comparer(
            field="album.artist",
            condition="ends_with",
            expected="an album",
        )

        model = adapter.validate_python(comparer)
        assert model.field == "Album Artist"
        assert model.comparison == "EndsWith"
        assert model.value == ["an album"]

    def test_parse_sub_comparers(self, model: _XMLCondition):
        assert model.And is None and model.Or is None
        comparers = ComparerFilter()

        # comparers aren't ready
        model.Or = _XMLConditions()
        model.parse_sub_comparers(combine=True, comparers=comparers)
        assert model.And is None and model.Or is None
        assert model.Or is None

        comparer = Comparer(
            field="album.artist",
            condition="ends_with",
            expected="an album",
        )
        comparers = ComparerFilter(comparers=comparer)
        model.Or = _XMLConditions()

        model.parse_sub_comparers(combine=True, comparers=comparers)
        assert model.And is not None and model.Or is None
        model.parse_sub_comparers(combine=False, comparers=comparers)
        assert model.And is None and model.Or is not None

    def test_parse_xml(self, adapter: TypeAdapter[_XMLCondition]):
        xml = {"@Comparison": "InRange", "@Field": "TrackNo", "@Value1": "10", "@Value2": "20"}
        assert adapter.validate_python(xml).model_dump_xml() == xml


class TestXMLConditions(BaseModelTester):

    @pytest.fixture
    def model(self) -> _XMLConditions:
        return _XMLConditions()

    def test_build_comparers(self, model: _XMLConditions):
        condition1 = _XMLCondition(
            field="TrackNo",
            comparison="IsIn",
            value=["a", "b", "c"],
            And=_XMLConditions(condition=[_XMLCondition(value=["a", "b", "c"])]),
        )
        condition2 = _XMLCondition(
            field="Album Artist",
            comparison="EndsWith",
            value=["an album"],
            Or=_XMLConditions(condition=[_XMLCondition(value=["a", "b", "c"])])
        )

        model.condition = [condition1, condition2]
        model.combine_method = choice(("All", "Any"))

        assert model.comparers == ComparerFilter[LocalTrack](
            comparers={
                condition1.comparer: (True, condition1.And.comparers),
                condition2.comparer: (False, condition2.Or.comparers),
            },
            match_all=model.combine_method == "All",
        )

    def test_parse_comparers(self, model: _XMLConditions, faker: Faker):
        condition1 = _XMLCondition()
        condition1.field = "TrackNo"
        condition1.comparison = "IsIn"
        condition1.value = ["a", "b", "c"]
        condition1.And = _XMLConditions(condition=[_XMLCondition(comparison="IsIn", value=["1", "2", "3"])])

        condition2 = _XMLCondition()
        condition2.field = "Album Artist"
        condition2.comparison = "EndsWith"
        condition2.value = "an album"
        condition2.Or = _XMLConditions(condition=[_XMLCondition(comparison="IsIn", value=["4", "5", "6"])])

        comparers = ComparerFilter[LocalTrack](
            comparers={
                condition1.comparer: (True, condition1.And.comparers),
                condition2.comparer: (False, condition2.Or.comparers),
            },
            match_all=faker.boolean(),
        )

        model = model.model_validate(comparers)
        assert model.combine_method == "All" if comparers.match_all else "Any"
        assert model.condition == [condition1, condition2]

    def test_parse_xml(self, adapter: TypeAdapter[_XMLConditions]):
        xml = {
            "@CombineMethod": choice(("All", "Any")),
            "Condition": [
                {"@Comparison": "InRange", "@Field": "TrackNo", "@Value1": "10", "@Value2": "20"},
                {"@Comparison": "Is", "@Field": "Album Artist", "@Value": "an album"},
            ]
        }
        assert adapter.validate_python(xml).model_dump_xml() == xml


class TestXMLLimit(BaseModelTester):
    @pytest.fixture
    def model(self) -> _XMLLimit:
        return _XMLLimit()

    def test_validate_limit_type_exists(self):
        model = _XMLLimit()

        with pytest.raises(ValueError):
            model.limit_type = "NotALimitType"

        expected = to_pascal(choice([enum for enum in LimitType]).name)
        model.type = expected
        assert model.type == expected

    def test_build_limiter(self, model: _XMLLimit):
        model.enabled = True
        model.count = 25
        model.type = "Minutes"
        model.selected_by = "MostRecentlyAdded"

        limiter = model.limiter
        assert limiter.limit_by == 25
        assert limiter.kind == LimitType.MINUTES
        assert limiter.sorted_by == "most_recently_added"
        assert limiter.allowance == 1.25

        model.enabled = False
        assert model.limiter is None

    def test_parse_limiter(self, model: _XMLLimit):
        limiter = ItemLimiter(
            limit_by=23,
            on=LimitType.HOURS,
            sorted_by="most_often_played",
        )

        model = model.model_validate(limiter)
        assert not model.filter_duplicates
        assert model.enabled
        assert model.count == 23
        assert model.type == "Hours"
        assert model.selected_by == "MostOftenPlayed"

        model.parse_limiter(filter_duplicates=True)
        assert not model.enabled
        assert model.filter_duplicates

    def test_parse_xml(self, adapter: TypeAdapter[_XMLLimit], faker: Faker):
        xml = {
            "@FilterDuplicates": faker.boolean(),
            "@Enabled": faker.boolean(),
            "@Count": faker.random_int(1, 100),
            "@Type": to_pascal(choice([enum for enum in LimitType]).name),
            "@SelectedBy": choice((
                "Random",
                "LeastRecentlyAdded",
                "MostRecentlyAdded",
                "LeastOftenPlayed",
                "MostOftenPlayed",
                "HighestRated",
                "LowestRated",
            ))
        }
        assert adapter.validate_python(xml).model_dump_xml() == xml


class TestXMLDisplayField(BaseModelTester):
    @staticmethod
    def get_valid_code() -> int:
        """Returns a random valid field code."""
        code = -1
        name = None
        while code <= 0 or name is None or name not in _XMLCondition.name_field_map:
            code, name = choice(tuple(_XMLCondition.code_name_map.items()))
        return code

    @pytest.fixture
    def model(self) -> _XMLDisplayField:
        return _XMLDisplayField(code=self.get_valid_code(), width=100)

    def test_validate_code_is_mapped(self, model: _XMLDisplayField):
        with pytest.raises(ValueError):
            _XMLDisplayField(code=9999)

    def test_field(self, model: _XMLDisplayField):
        assert model.field in _XMLCondition.field_name_map

    def test_parse_xml(self, adapter: TypeAdapter[_XMLDisplayField], faker: Faker):
        xml = {"@Code": self.get_valid_code(), "@Width": faker.random_int(1, 100)}
        assert adapter.validate_python(xml).model_dump_xml() == xml


class TestXMLDisplayGroup(BaseModelTester):
    @pytest.fixture
    def model(self) -> _XMLDisplayGroup:
        return _XMLDisplayGroup(id="TrackDetail", field=[
            _XMLDisplayField(code=20, width=24),
            _XMLDisplayField(code=78, width=48),
            _XMLDisplayField(code=65, width=769),
        ])

    def test_parse_xml(self, adapter: TypeAdapter[_XMLDisplayGroup], faker: Faker):
        xml = {
            "@Id": choice(("TrackDetail", "Album")),
            "Field": [
                {
                    "@Code": TestXMLDisplayField.get_valid_code(),
                    "@Width": faker.random_int(1, 100)
                }
                for _ in range(faker.random_int(1, 10))
            ]
        }
        assert adapter.validate_python(xml).model_dump_xml() == xml


class TestXMLDisplayFields(BaseModelTester):
    @pytest.fixture
    def model(self) -> _XMLDisplayFields:
        return _XMLDisplayFields(
            group=[
                _XMLDisplayGroup(id="TrackDetail", field=[
                    _XMLDisplayField(code=20, width=24),
                    _XMLDisplayField(code=78, width=48),
                    _XMLDisplayField(code=65, width=769),
                ]),
                _XMLDisplayGroup(id="Album", field=[
                    _XMLDisplayField(code=20, width=16),
                    _XMLDisplayField(code=78, width=25),
                    _XMLDisplayField(code=31, width=135),
                    _XMLDisplayField(code=54, width=40),
                    _XMLDisplayField(code=65, width=160),
                    _XMLDisplayField(code=30, width=110),
                    _XMLDisplayField(code=59, width=130),
                    _XMLDisplayField(code=75, width=75),
                    _XMLDisplayField(code=16, width=34),
                    _XMLDisplayField(code=12, width=75),
                ])
            ]
        )

    def test_parse_xml(self, adapter: TypeAdapter[_XMLDisplayFields], faker: Faker):
        xml = {
            "Group": [
                {
                    "@Id": choice(("TrackDetail", "Album")),
                    "Field": [
                        {"@Code": TestXMLDisplayField.get_valid_code(), "@Width": faker.random_int(1, 100)}
                        for _ in range(faker.random_int(1, 10))
                    ]
                }
                for _ in range(faker.random_int(1, 3))
            ]
        }
        assert adapter.validate_python(xml).model_dump_xml() == xml


class TestXMLSortBy(BaseModelTester):
    @pytest.fixture
    def model(self) -> _XMLSortBy:
        return _XMLSortBy()

    def test_validate_field_is_mapped(self, model: _XMLCondition):
        with pytest.raises(ValueError):
            model.field = 9999

        model.field = TestXMLDisplayField.get_valid_code()

    def test_field_name(self, model: _XMLSortBy):
        model.field = TestXMLDisplayField.get_valid_code()
        assert model.field_name in _XMLCondition.field_name_map

    def test_parse_sorter_fails_on_unknown_fields(self, model: _XMLSortBy):
        sorter = ItemSorter(sort_fields={"released_at": True})
        with pytest.raises(ValueError):
            model.parse_sorter(sorter=sorter)

    def test_parse_sorter_fails_on_too_many_fields(self, model: _XMLSortBy, faker: Faker):
        sorter = ItemSorter(sort_fields={choice(tuple(SORT_FIELDS)): faker.boolean() for _ in range(3)})
        with pytest.raises(ValueError):
            model.parse_sorter(sorter=sorter)

    def test_parse_sorter(self, model: _XMLSortBy, faker: Faker):
        field = "name"
        sorter = ItemSorter(sort_fields={field: faker.boolean()})

        model.parse_sorter(sorter=sorter)
        assert model.field_name == field
        assert model.order == "Descending" if sorter.sort_fields[field] else "Ascending"

    def test_parse_xml(self, adapter: TypeAdapter[_XMLSortBy]):
        xml = {
            "@Field": TestXMLDisplayField.get_valid_code(),
            "@Order": choice(("Ascending", "Descending"))
        }
        assert adapter.validate_python(xml).model_dump_xml() == xml


class TestDefinedSort(BaseModelTester):
    @pytest.fixture
    def model(self) -> _XMLDefinedSort:
        return _XMLDefinedSort(id=choice(tuple(_XMLDefinedSort.fields_map)))

    def test_validate_id_is_mapped(self, model: _XMLDefinedSort):
        with pytest.raises(ValueError):
            model.id = 9999

        model.id = choice(tuple(_XMLDefinedSort.fields_map))

    def test_fields_map_has_valid_fields(self, model: _XMLDefinedSort):
        for fields in _XMLDefinedSort.fields_map.values():
            for field in fields:
                assert field in _XMLCondition.name_field_map

    def test_parse_sorter_fails_on_unknown_fields(self, model: _XMLDefinedSort):
        sorter = ItemSorter(sort_fields={"released_at": True, "compilation": False})
        with pytest.raises(ValueError, match="Field code mapping not found"):
            model.parse_sorter(sorter=sorter)

    def test_parse_sorter_fails_on_unknown_fields_map(self, model: _XMLDefinedSort):
        sorter = ItemSorter(sort_fields={"disc.number": True, "track.number": False})
        with pytest.raises(ValueError, match="No sort defined"):
            model.parse_sorter(sorter=sorter)

    def test_parse_sorter_fails_on_single_fields(self, model: _XMLDefinedSort, faker: Faker):
        sorter = ItemSorter(sort_fields={choice(tuple(SORT_FIELDS)): faker.boolean()})
        with pytest.raises(ValueError, match="Only use this sorter for multi-field sorts"):
            model.parse_sorter(sorter=sorter)

    def test_parse_sorter(self, model: _XMLDefinedSort):
        fields = choice(tuple(_XMLDefinedSort.fields_map.values()))
        sorter = ItemSorter(sort_fields={_XMLCondition.name_field_map[k]: v for k, v in fields.items()})
        model.parse_sorter(sorter=sorter)
        assert model.id == next((code for code, val in _XMLDefinedSort.fields_map.items() if val == fields), None)

    def test_parse_xml(self, adapter: TypeAdapter[_XMLDefinedSort]):
        xml = {"@Id": choice(tuple(_XMLDefinedSort.fields_map))}
        assert adapter.validate_python(xml).model_dump_xml() == xml


class TestXMLSource(BaseModelTester):
    @pytest.fixture
    def model(self) -> _XMLSource:
        return _XMLSource()

    def test_split_exceptions(self, model: _XMLSource):
        model.exceptions_include = "a|b|c"
        assert model.exceptions_include == {"a", "b", "c"}

        model.exceptions = "1|2|3"
        assert model.exceptions == {"1", "2", "3"}

    def test_join_exceptions(self, model: _XMLSource):
        model.exceptions_include = {"a", "b", "c"}
        assert model.model_dump(include={"exceptions_include"})["exceptions_include"] == "a|b|c"

        model.exceptions = {"1", "2", "3"}
        assert model.model_dump(include={"exceptions"})["exceptions"] == "1|2|3"

    def test_parse_matcher_when_none(self, model: _XMLSource):
        model.conditions = _XMLConditions(condition=[_XMLCondition(value=["a", "b", "c"])])
        model.exceptions_include = {"a", "b", "c"}
        model.exceptions = {"1", "2", "3"}

        model.parse_matcher()
        assert model.conditions == _XMLConditions()
        assert model.exceptions_include is None
        assert model.exceptions is None

    def test_parse_matcher(self, model: _XMLSource):
        matcher = MatchFilter(
            compare=ComparerFilter[LocalTrack](),
            include=PathsFilter(values={"a", "b", "c"}),
            exclude=PathsFilter(values={"1", "2", "3"}),
            group_by="album",
        )

        model.parse_matcher(matcher)
        assert model.conditions.comparers == ComparerFilter[LocalTrack]()
        assert model.exceptions_include == {"a", "b", "c"}
        assert model.exceptions == {"1", "2", "3"}

    def test_parse_sorter_when_none(self, model: _XMLSource):
        model.sort_by = _XMLSortBy()
        model.parse_sorter()
        assert model.sort_by is None

    def test_parse_sorter(self, model: _XMLSource):
        fields = choice(tuple(_XMLDefinedSort.fields_map.values()))
        sorter = ItemSorter(sort_fields={_XMLCondition.name_field_map[k]: v for k, v in fields.items()})

        model.parse_sorter(sorter=sorter)
        assert isinstance(model.sort_by, _XMLDefinedSort)

        sorter.sort_fields = dict([choice(tuple(sorter.sort_fields.items()))])
        model.parse_sorter(sorter=sorter)
        assert isinstance(model.sort_by, _XMLSortBy)

    def test_parse_xml(self, adapter: TypeAdapter[_XMLSource], faker: Faker):
        xml = {
            "@Type": faker.random_int(1, 10),
            "Description": faker.sentence(),
            "Conditions": {
                "@CombineMethod": choice(("All", "Any")),
                "Condition": [
                    {"@Comparison": "InRange", "@Field": "TrackNo", "@Value1": "10", "@Value2": "20"},
                    {"@Comparison": "Is", "@Field": "Album Artist", "@Value": "an album"},
                    {"@Comparison": "IsNull", "@Field": "ArtistPeople"},
                ]
            },
            "Limit": {
                "@FilterDuplicates": faker.boolean(),
                "@Enabled": faker.boolean(),
                "@Count": faker.random_int(1, 100),
                "@Type": to_pascal(choice([enum for enum in LimitType]).name),
                "@SelectedBy": choice((
                    "Random",
                    "LeastRecentlyAdded",
                    "MostRecentlyAdded",
                    "LeastOftenPlayed",
                    "MostOftenPlayed",
                    "HighestRated",
                    "LowestRated",
                ))
            },
            "Fields": {
                "Group": [
                    {
                        "@Id": choice(("TrackDetail", "Album")),
                        "Field": [
                            {
                                "@Code": TestXMLDisplayField.get_valid_code(),
                                "@Width": faker.random_int(1, 100)
                            }
                            for _ in range(faker.random_int(1, 10))
                        ]
                    },
                ]
            },
            "ExceptionsInclude": "|".join(sorted(faker.file_path() for _ in range(faker.random_int(1, 10)))),
            "Exceptions": "|".join(sorted(faker.file_path() for _ in range(faker.random_int(1, 10)))),
        }

        if faker.boolean():
            xml["SortBy"] = {
                "@Field": TestXMLDisplayField.get_valid_code(),
                "@Order": choice(("Ascending", "Descending"))
            }
        else:
            xml["DefinedSort"] = {
                "@Id": choice(tuple(_XMLDefinedSort.fields_map))
            }

        assert adapter.validate_python(xml).model_dump_xml() == xml


class TestXMLSmartPlaylist(BaseModelTester):
    @pytest.fixture
    def model(self) -> _XMLSmartPlaylist:
        return _XMLSmartPlaylist()

    def test_build_matcher(self, model: _XMLSmartPlaylist):
        model.group_by = "album"
        model.source.exceptions_include = {"a", "b", "c"}
        model.source.exceptions = {"1", "2", "3"}

        assert model.matcher.compare == model.source.conditions.comparers
        assert model.matcher.include.values == model.source.exceptions_include
        assert model.matcher.exclude.values == model.source.exceptions
        assert model.matcher.group_by == model.group_by

    def test_build_matcher_drops_group_by_on_tracks(self, model: _XMLSmartPlaylist):
        model.group_by = "track"
        assert model.matcher.group_by is None

    def test_parse_matcher_when_none(self, model: _XMLSmartPlaylist):
        model.group_by = "track"
        model.parse_matcher()
        assert model.group_by == _XMLSmartPlaylist.model_fields["group_by"].default

    def test_parse_matcher_with_no_group_by(self, model: _XMLSmartPlaylist):
        matcher = MatchFilter(group_by=None)
        model.parse_matcher(matcher)
        assert model.group_by == _XMLSmartPlaylist.model_fields["group_by"].default

    def test_parse_matcher(self, model: _XMLSmartPlaylist, mocker: MockerFixture):
        matcher = MatchFilter(
            compare=ComparerFilter[LocalTrack](),
            include=PathsFilter(values={"a", "b", "c"}),
            exclude=PathsFilter(values={"1", "2", "3"}),
            group_by="album",
        )

        mock_parse = mocker.spy(_XMLSource, "parse_matcher")

        model.parse_matcher(matcher)

        mock_parse.assert_called_once_with(model.source, matcher)
        assert model.group_by == matcher.group_by

    def test_build_sorter(self, model: _XMLSmartPlaylist, faker: Faker):
        model.shuffle_mode = "RecentAdded"
        model.shuffle_same_artist_weight = faker.random_int(-10, 10) / 10
        model.source.sort_by = _XMLDefinedSort(id=choice(tuple(_XMLDefinedSort.fields_map.keys())))

        assert model.sorter.sort_fields == model.source.sort_by.sort_fields
        assert model.sorter.shuffle_mode == ShuffleMode.RECENT_ADDED
        assert model.sorter.shuffle_weight == model.shuffle_same_artist_weight

    def test_parse_sorter_when_none(self, model: _XMLSmartPlaylist):
        model.parse_sorter()
        assert model.shuffle_mode == _XMLSmartPlaylist.model_fields["shuffle_mode"].default
        shuffle_same_artist_weight_default = _XMLSmartPlaylist.model_fields["shuffle_same_artist_weight"].default
        assert model.shuffle_same_artist_weight == shuffle_same_artist_weight_default

    def test_parse_sorter_with_no_options(self, model: _XMLSmartPlaylist, faker: Faker):
        sorter = ItemSorter(sort_fields={"name": faker.boolean()})

        model.parse_sorter(sorter)
        assert model.shuffle_mode == _XMLSmartPlaylist.model_fields["shuffle_mode"].default
        assert model.shuffle_same_artist_weight == sorter.shuffle_weight

    def test_parse_sorter(self, model: _XMLSmartPlaylist, mocker: MockerFixture, faker: Faker):
        sorter = ItemSorter(
            sort_fields={"name": faker.boolean()},
            shuffle_mode=ShuffleMode.RECENT_ADDED,
            shuffle_weight=faker.random_int(-10, 10) / 10,
        )

        mock_parse = mocker.spy(_XMLSource, "parse_sorter")

        model.parse_sorter(sorter)

        mock_parse.assert_called_once_with(model.source, sorter)
        assert model.shuffle_mode == to_pascal(sorter.shuffle_mode.name)
        assert model.shuffle_same_artist_weight == sorter.shuffle_weight

    def test_parse_xml(self, adapter: TypeAdapter[_XMLSmartPlaylist], faker: Faker):
        xml = {
            "@SaveStaticCopy": faker.boolean(),
            "@LiveUpdating": faker.boolean(),
            "@Layout": faker.random_int(0, 10),
            "@LayoutGroupBy": faker.random_int(0, 10),
            "@ShuffleMode": to_pascal(choice([enum for enum in ShuffleMode]).name),
            "@ShuffleSameArtistWeight": faker.random_int(0, 10) / 10,
            "@GroupBy": faker.random_element(Track.__tag_attributes__),
            "@ConsolidateAlbums": faker.boolean(),
            "@MusicLibraryPath": faker.file_path(),
        }
        result = adapter.validate_python(xml).model_dump_xml()
        result.pop("Source")  # Source is tested separately
        assert result == xml


class TestXMLRoot(BaseModelTester):
    @pytest.fixture
    def model(self) -> _XMLRoot:
        return _XMLRoot()

    @pytest.mark.skipif(not required_modules_installed(REQUIRED_MODULES), reason="xmltodict not installed")
    def test_parse_xml(self, adapter: TypeAdapter, xml_playlist: str):
        model = _XMLRoot.model_validate(xml_playlist)
        assert model.unparse_xml() == xml_playlist
