import os
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from random import choice
from unittest import mock

import pytest
from faker import Faker
from pydantic import TypeAdapter
from pydantic.alias_generators import to_pascal

# noinspection PyProtectedMember
from musify.local.collection.playlist.xautopf import REQUIRED_MODULES, XAutoPF, _XMLCondition, _XMLConditions, \
    _XMLLimit, _XMLDisplayField, _XMLDisplayGroup, _XMLSortBy, _XMLDefinedSort, _XMLSource, _XMLSmartPlaylist, _XMLRoot, \
    _XMLDisplayFields
from musify.local.item.track import LocalTrack
from musify.models.properties.file import PathMapper, PathStemMapper
from musify.processors_new.compare import Comparer, COMPARISON_FIELDS
from musify.processors_new.filters import ComparerFilter, PathsFilter, MatchFilter
from musify.processors_new.limit import LimitType, ItemLimiter
from musify.processors_new.sort import ShuffleMode, ItemSorter, SORT_FIELDS
from musify.utils import required_modules_installed
from tests.models.testers import UniqueKeyTester, MusifyModelTester


@pytest.fixture
def xml_playlist_basic() -> str:
    """A basic XAutoPF playlist XML structure for testing purposes."""
    return """
<?xml version="1.0" encoding="utf-8"?>
<SmartPlaylist SaveStaticCopy="True" LiveUpdating="True" Layout="0" LayoutGroupBy="0" ShuffleMode="RecentAdded" ShuffleSameArtistWeight="0.5" GroupBy="album" ConsolidateAlbums="False" MusicLibraryPath="/mnt/d/Music/">
  <Source Type="1">
    <Description>I am a description</Description>
    <Conditions CombineMethod="All">
      <Condition Field="Album" Comparison="Contains" Value="an album" />
      <Condition Field="ArtistPeople" Comparison="IsNull" />
      <Condition Field="TrackNo" Comparison="LessThan" Value="30" />
    </Conditions>
    <Limit FilterDuplicates="False" Enabled="False" Count="25" Type="Minutes" SelectedBy="MostRecentlyAdded" />
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
    return """
<?xml version="1.0" encoding="utf-8"?>
<SmartPlaylist SaveStaticCopy="True" LiveUpdating="True" Layout="0" LayoutGroupBy="0" ShuffleMode="RecentAdded" ShuffleSameArtistWeight="0.5" GroupBy="album" ConsolidateAlbums="False" MusicLibraryPath="/mnt/d/Music/">
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
    <Limit FilterDuplicates="False" Enabled="True" Count="1" Type="Seconds" SelectedBy="MostRecentlyAdded" />
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


@pytest.fixture
def xml_playlist_recent() -> str:
    """A recently added tracks XAutoPF playlist XML structure for testing purposes."""
    return """
<?xml version="1.0" encoding="utf-8"?>
<SmartPlaylist SaveStaticCopy="False" LiveUpdating="True" Layout="4" LayoutGroupBy="0" ShuffleMode="DifferentArtist" ShuffleSameArtistWeight="-0.2" GroupBy="track" ConsolidateAlbums="False" MusicLibraryPath="/mnt/d/Music/">
  <Source Type="1">
    <Conditions CombineMethod="Any">
      <Condition Field="Album" Comparison="Contains" Value="" />
    </Conditions>
    <Limit FilterDuplicates="True" Enabled="True" Count="20" Type="Items" SelectedBy="MostRecentlyAdded" />
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


class TestXAutoPF(UniqueKeyTester):

    @pytest.fixture
    async def model(self, tracks: list[LocalTrack], faker: Faker, tmp_path: Path) -> XAutoPF:
        playlist = XAutoPF(path=tmp_path.joinpath(faker.file_path(absolute=False, extension="xautopf")))
        return await playlist.load(tracks=tracks)

    @pytest.fixture
    def path_mapper(self, tracks: list[LocalTrack]) -> PathStemMapper:
        """Creates a basic PathStemMapper for the given tracks."""
        stem_map = {str(parent): "./" for parent in set(track.path.parent for track in tracks)}
        return PathStemMapper(stem_map=stem_map)

    @staticmethod
    async def assert_load(
            path: Path,
            xml: _XMLRoot,
            tracks: list[LocalTrack],
            path_mapper: PathMapper
    ) -> None:
        """Asserts loading of a playlist from a given path with expected XML structure and tracks."""
        pl = XAutoPF(path=path, path_mapper=path_mapper)
        assert pl._xml is None
        assert not pl.tracks
        assert not pl.description
        assert not pl.matcher
        assert not pl.limiter
        assert not pl.sorter

        await pl.load()
        assert pl._xml == xml
        assert not pl.tracks
        assert pl.description == xml.smart_playlist.source.description

        matcher = xml.smart_playlist.matcher
        matcher.include.path_mapper = path_mapper
        matcher.exclude.path_mapper = path_mapper
        assert pl.matcher == matcher
        assert pl.limiter == xml.smart_playlist.source.limit.limiter
        assert pl.sorter == xml.smart_playlist.sorter

        with (
            mock.patch.object(XAutoPF, "_match", return_value=None) as mock_match,
            mock.patch.object(XAutoPF, "_limit", return_value=None) as mock_limit,
            mock.patch.object(XAutoPF, "_sort", return_value=None) as mock_sort,
        ):
            await pl.load(tracks)

            mock_match.assert_called_once_with(tracks=tracks, reference=tracks[0])
            mock_limit.assert_called_once_with(ignore=pl.matcher.exclude.values)
            mock_sort.assert_called_once_with()

    async def test_load_from_no_file(
            self,
            model: XAutoPF,
            xml_playlist: str,
            tracks: list[LocalTrack],
            path_mapper: PathMapper,
            faker: Faker,
            tmp_path: Path
    ):
        await self.assert_load(model.path, _XMLRoot(), tracks, path_mapper)

    async def test_load_from_file(
            self,
            model: XAutoPF,
            xml_playlist: str,
            tracks: list[LocalTrack],
            path_mapper: PathMapper,
            faker: Faker,
            tmp_path: Path
    ):
        model.path.parent.mkdir(parents=True, exist_ok=True)
        with model.path.open("w", encoding="utf-8") as file:
            file.write(xml_playlist)

        xml = _XMLRoot.model_validate(xml_playlist)
        await self.assert_load(model.path, xml, tracks, path_mapper)

    async def test_limiter_deduplication(
            self,
            model: XAutoPF,
            xml_playlist_recent: str,
            tracks: list[LocalTrack],
            path_mapper: PathMapper,
            faker: Faker
    ):
        model.path.parent.mkdir(parents=True, exist_ok=True)
        with model.path.open("w", encoding="utf-8") as file:
            file.write(xml_playlist_recent)

        for track in tracks:
            track.added_at = datetime(2024, 1, faker.random_int(1, 28))

        pl = XAutoPF(path=model.path)
        await pl.load()
        assert not pl.tracks
        assert pl.limiter_deduplication

        limit = pl.limiter.limit_by
        tracks_expected = sorted(tracks, key=lambda t: t.added_at, reverse=True)[:limit]

        await pl.load(tracks)
        assert pl.tracks == tracks_expected

        # add duplicates and apply deduplication
        await pl.load(tracks=tracks + tracks)
        assert pl.tracks == tracks_expected

    async def test_save_to_new_file(self, faker: Faker, tmp_path: Path):
        path = tmp_path.joinpath(faker.file_path(absolute=False, extension="xautopf"))
        pl = XAutoPF(path=path)

        await pl.load()
        assert not path.exists()
        assert not pl.tracks  # no tracks given so no tracks loaded
        assert pl._xml

        await pl.save(dry_run=True)
        assert not path.exists()
        await pl.save(dry_run=False)
        assert path.is_file()

        with path.open("r") as file:
            assert file.read() == pl._xml.unparse_xml()

    async def test_save_to_existing_file(
            self, tracks: list[LocalTrack], path_mapper: PathMapper, tmp_path: Path
    ):
        path = path_playlist_xautopf_bp
        # prepare tracks to search through
        tracks_actual = [track for track in tracks if track.path in [path_track_flac, path_track_wma]]
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
        original_dt_modified = pl.added_at
        original_dt_created = pl.created_at
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


class TestXMLCondition(MusifyModelTester):

    @pytest.fixture
    def model(self) -> _XMLCondition:
        return _XMLCondition()

    def test_all_fields_have_codes(self):
        assert not set(_XMLCondition.name_field_map) - set(_XMLCondition.name_code_map)

    def test_reference_required(self, model: _XMLCondition) -> None:
        assert model.reference_values

        model.value = [choice(list(model.reference_values))]
        assert model.reference_required

        model.value = ["not a reference value"]
        assert not model.reference_required

    def test_merge_values(self, adapter: TypeAdapter[_XMLCondition]) -> None:
        model = adapter.validate_python({"@Value": "a"})
        assert model.value == ["a"]

        model = adapter.validate_python(
            {"@Value1": "a", "@Value2": "b", "@Value3": "c", "@Value4": "d"}
        )
        assert model.value == ["a", "b", "c", "d"]

        model.value = ["1", "2", "3"]
        assert model.value == ["1", "2", "3"]

    def test_validate_field_is_mapped(self, model: _XMLCondition) -> None:
        with pytest.raises(ValueError):
            model.field = "NotAField"

        model.field = choice(tuple(model.name_field_map))

    def test_validate_only_and_either_or_set(self, model: _XMLCondition) -> None:
        assert model.And is None and model.Or is None
        model.And = _XMLConditions()
        with pytest.raises(ValueError):
            model.Or = _XMLConditions()

        model.And = None
        model.Or = _XMLConditions()
        with pytest.raises(ValueError):
            model.And = _XMLConditions()

    def test_build_comparer(self, model: _XMLCondition) -> None:
        model.field = "TrackNo"
        model.comparison = "IsIn"
        model.value = ["a", "b", "c"]

        comparer = model.comparer
        assert comparer == Comparer(
            field="track_number",
            condition="IsIn",
            expected=["a", "b", "c"],
            reference_required=model.reference_required,
        )

    def test_parse_comparer(self, adapter: TypeAdapter[_XMLCondition]) -> None:
        comparer = Comparer(
            field="album_artist",
            condition="ends_with",
            expected="an album",
        )

        model = adapter.validate_python(comparer)
        assert model.field == "Album Artist"
        assert model.comparison == "EndsWith"
        assert model.value == ["an album"]

    def test_parse_sub_comparers(self, model: _XMLCondition) -> None:
        assert model.And is None and model.Or is None
        comparers = ComparerFilter()

        # comparers aren't ready
        model.Or = _XMLConditions()
        model.parse_sub_comparers(combine=True, comparers=comparers)
        assert model.And is None and model.Or is None
        assert model.Or is None

        comparer = Comparer(
            field="album_artist",
            condition="ends_with",
            expected="an album",
        )
        comparers = ComparerFilter(comparers=comparer)
        model.Or = _XMLConditions()

        model.parse_sub_comparers(combine=True, comparers=comparers)
        assert model.And is not None and model.Or is None
        model.parse_sub_comparers(combine=False, comparers=comparers)
        assert model.And is None and model.Or is not None

    def test_parse_xml(self, adapter: TypeAdapter[_XMLCondition]) -> None:
        xml = {"@Comparison": "InRange", "@Field": "TrackNo", "@Value1": "10", "@Value2": "20"}
        assert adapter.validate_python(xml).model_dump_xml() == xml


class TestXMLConditions(MusifyModelTester):

    @pytest.fixture
    def model(self) -> _XMLConditions:
        return _XMLConditions()

    def test_build_comparers(self, model: _XMLConditions) -> None:
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
        model.combine_method = choice(["All", "Any"])

        assert model.comparers == ComparerFilter[LocalTrack](
            comparers={
                condition1.comparer: (True, condition1.And.comparers),
                condition2.comparer: (False, condition2.Or.comparers),
            },
            match_all=model.combine_method == "All",
        )

    def test_parse_comparers(self, model: _XMLConditions) -> None:
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
            match_all=choice([True, False]),
        )

        model = model.model_validate(comparers)
        assert model.combine_method == "All" if comparers.match_all else "Any"
        assert model.condition == [condition1, condition2]

    def test_parse_xml(self, adapter: TypeAdapter[_XMLConditions]) -> None:
        xml = {
            "@CombineMethod": choice(["All", "Any"]),
            "Condition": [
                {"@Comparison": "InRange", "@Field": "TrackNo", "@Value1": "10", "@Value2": "20"},
                {"@Comparison": "Is", "@Field": "Album Artist", "@Value": "an album"},
            ]
        }
        assert adapter.validate_python(xml).model_dump_xml() == xml


class TestXMLLimit(MusifyModelTester):
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

    def test_build_limiter(self, model: _XMLLimit) -> None:
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

    def test_parse_limiter(self, model: _XMLLimit) -> None:
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

    def test_parse_xml(self, adapter: TypeAdapter[_XMLLimit], faker: Faker) -> None:
        xml = {
            "@FilterDuplicates": choice([True, False]),
            "@Enabled": choice([True, False]),
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


class TestXMLDisplayField(MusifyModelTester):
    @staticmethod
    def get_valid_code() -> int:
        """Returns a random valid field code."""
        code = 0
        while code in (0, 20, 78):
            code = choice(tuple(_XMLCondition.code_name_map))
        return code

    @pytest.fixture
    def model(self) -> _XMLDisplayField:
        return _XMLDisplayField(code=self.get_valid_code(), width=100)

    def test_validate_code_is_mapped(self, model: _XMLDisplayField) -> None:
        with pytest.raises(ValueError):
            _XMLDisplayField(code=9999)

    def test_field(self, model: _XMLDisplayField) -> None:
        assert model.field in _XMLCondition.field_name_map

    def test_parse_xml(self, adapter: TypeAdapter[_XMLDisplayField], faker: Faker) -> None:
        xml = {"@Code": self.get_valid_code(), "@Width": faker.random_int(1, 100)}
        assert adapter.validate_python(xml).model_dump_xml() == xml


class TestXMLDisplayGroup(MusifyModelTester):
    @pytest.fixture
    def model(self) -> _XMLDisplayGroup:
        return _XMLDisplayGroup(id="TrackDetail", field=[
            _XMLDisplayField(code=20, width=24),
            _XMLDisplayField(code=78, width=48),
            _XMLDisplayField(code=65, width=769),
        ])

    def test_parse_xml(self, adapter: TypeAdapter[_XMLDisplayGroup], faker: Faker) -> None:
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


class TestXMLDisplayFields(MusifyModelTester):
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

    def test_parse_xml(self, adapter: TypeAdapter[_XMLDisplayFields], faker: Faker) -> None:
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


class TestXMLSortBy(MusifyModelTester):
    @pytest.fixture
    def model(self) -> _XMLSortBy:
        return _XMLSortBy()

    def test_validate_field_is_mapped(self, model: _XMLCondition) -> None:
        with pytest.raises(ValueError):
            model.field = 9999

        model.field = TestXMLDisplayField.get_valid_code()

    def test_field_name(self, model: _XMLDisplayField) -> None:
        model.field = TestXMLDisplayField.get_valid_code()
        assert model.field_name in _XMLCondition.field_name_map

    def test_parse_sorter_fails_on_unknown_fields(self, model: _XMLSortBy) -> None:
        sorter = ItemSorter(sort_fields={"released_at": True})
        with pytest.raises(ValueError):
            model.parse_sorter(sorter=sorter)

    def test_parse_sorter_fails_on_too_many_fields(self, model: _XMLSortBy) -> None:
        sorter = ItemSorter(sort_fields={choice(tuple(SORT_FIELDS)): choice([True, False]) for _ in range(3)})
        with pytest.raises(ValueError):
            model.parse_sorter(sorter=sorter)

    def test_parse_sorter(self, model: _XMLSortBy) -> None:
        field = "name"
        sorter = ItemSorter(sort_fields={field: choice([True, False])})

        model.parse_sorter(sorter=sorter)
        assert model.field_name == field
        assert model.order == "Descending" if sorter.sort_fields[field] else "Ascending"

    def test_parse_xml(self, adapter: TypeAdapter[_XMLSortBy]) -> None:
        xml = {
            "@Field": TestXMLDisplayField.get_valid_code(),
            "@Order": choice(("Ascending", "Descending"))
        }
        assert adapter.validate_python(xml).model_dump_xml() == xml


class TestDefinedSort(MusifyModelTester):
    @pytest.fixture
    def model(self) -> _XMLDefinedSort:
        return _XMLDefinedSort(id=choice(tuple(_XMLDefinedSort.fields_map)))

    def test_validate_id_is_mapped(self, model: _XMLDefinedSort) -> None:
        with pytest.raises(ValueError):
            model.id = 9999

        model.id = choice(tuple(_XMLDefinedSort.fields_map))

    def test_fields_map_has_valid_fields(self, model: _XMLDefinedSort) -> None:
        for fields in _XMLDefinedSort.fields_map.values():
            for field in fields:
                assert field in _XMLCondition.name_field_map

    def test_parse_sorter_fails_on_unknown_fields(self, model: _XMLSortBy) -> None:
        sorter = ItemSorter(sort_fields={"released_at": True, "compilation": False})
        with pytest.raises(ValueError, match="Field code mapping not found"):
            model.parse_sorter(sorter=sorter)

    def test_parse_sorter_fails_on_unknown_fields_map(self, model: _XMLSortBy) -> None:
        sorter = ItemSorter(sort_fields={"disc_number": True, "track_number": False})
        with pytest.raises(ValueError, match="No sort defined"):
            model.parse_sorter(sorter=sorter)

    def test_parse_sorter_fails_on_single_fields(self, model: _XMLSortBy) -> None:
        sorter = ItemSorter(sort_fields={choice(tuple(SORT_FIELDS)): choice([True, False])})
        with pytest.raises(ValueError, match="Only use this sorter for multi-field sorts"):
            model.parse_sorter(sorter=sorter)

    def test_parse_sorter(self, model: _XMLSortBy) -> None:
        fields = choice(tuple(_XMLDefinedSort.fields_map.values()))
        sorter = ItemSorter(sort_fields={_XMLCondition.name_field_map[k]: v for k, v in fields.items()})
        model.parse_sorter(sorter=sorter)
        assert model.id == next((code for code, val in _XMLDefinedSort.fields_map.items() if val == fields), None)

    def test_parse_xml(self, adapter: TypeAdapter[_XMLSortBy]) -> None:
        xml = {"@Id": choice(tuple(_XMLDefinedSort.fields_map))}
        assert adapter.validate_python(xml).model_dump_xml() == xml


class TestXMLSource(MusifyModelTester):
    @pytest.fixture
    def model(self) -> _XMLSource:
        return _XMLSource()

    def test_split_exceptions(self, model: _XMLSource) -> None:
        model.exceptions_include = "a|b|c"
        assert model.exceptions_include == {"a", "b", "c"}

        model.exceptions = "1|2|3"
        assert model.exceptions == {"1", "2", "3"}

    def test_join_exceptions(self, model: _XMLSource) -> None:
        model.exceptions_include = {"a", "b", "c"}
        assert model.model_dump(include={"exceptions_include"})["exceptions_include"] == "a|b|c"

        model.exceptions = {"1", "2", "3"}
        assert model.model_dump(include={"exceptions"})["exceptions"] == "1|2|3"

    def test_parse_matcher_when_none(self, model: _XMLSource) -> None:
        model.conditions = _XMLConditions(condition=[_XMLCondition(value=["a", "b", "c"])])
        model.exceptions_include = {"a", "b", "c"}
        model.exceptions = {"1", "2", "3"}

        model.parse_matcher()
        assert model.conditions == _XMLConditions()
        assert model.exceptions_include is None
        assert model.exceptions is None

    def test_parse_matcher(self, model: _XMLSource) -> None:
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

    def test_parse_sorter_when_none(self, model: _XMLSource) -> None:
        model.sort_by = _XMLSortBy()
        model.parse_sorter()
        assert model.sort_by is None

    def test_parse_sorter(self, model: _XMLSource) -> None:
        fields = choice(tuple(_XMLDefinedSort.fields_map.values()))
        sorter = ItemSorter(sort_fields={_XMLCondition.name_field_map[k]: v for k, v in fields.items()})

        model.parse_sorter(sorter=sorter)
        assert isinstance(model.sort_by, _XMLDefinedSort)

        sorter.sort_fields = dict([choice(tuple(sorter.sort_fields.items()))])
        model.parse_sorter(sorter=sorter)
        assert isinstance(model.sort_by, _XMLSortBy)

    def test_parse_xml(self, adapter: TypeAdapter[_XMLSource], faker: Faker) -> None:
        xml = {
            "@Type": faker.random_int(1, 10),
            "Description": faker.sentence(),
            "Conditions": {
                "@CombineMethod": choice(["All", "Any"]),
                "Condition": [
                    {"@Comparison": "InRange", "@Field": "TrackNo", "@Value1": "10", "@Value2": "20"},
                    {"@Comparison": "Is", "@Field": "Album Artist", "@Value": "an album"},
                    {"@Comparison": "IsNull", "@Field": "ArtistPeople"},
                ]
            },
            "Limit": {
                "@FilterDuplicates": choice([True, False]),
                "@Enabled": choice([True, False]),
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
                                "@Width": faker.random_int(0, 100)
                            }
                            for _ in range(faker.random_int(1, 10))
                        ]
                    },
                ]
            },
            "ExceptionsInclude": "|".join(sorted(faker.file_path() for _ in range(faker.random_int(1, 10)))),
            "Exceptions": "|".join(sorted(faker.file_path() for _ in range(faker.random_int(1, 10)))),
        }

        if choice([True, False]):
            xml["SortBy"] = {
                "@Field": TestXMLDisplayField.get_valid_code(),
                "@Order": choice(["Ascending", "Descending"])
            }
        else:
            xml["DefinedSort"] = {
                "@Id": choice(tuple(_XMLDefinedSort.fields_map))
            }

        assert adapter.validate_python(xml).model_dump_xml() == xml


class TestXMLSmartPlaylist(MusifyModelTester):
    @pytest.fixture
    def model(self) -> _XMLSmartPlaylist:
        return _XMLSmartPlaylist()

    def test_build_matcher(self, model: _XMLSmartPlaylist) -> None:
        model.source.exceptions_include = {"a", "b", "c"}
        model.source.exceptions = {"1", "2", "3"}

        assert model.matcher.compare == model.source.conditions.comparers
        assert model.matcher.include.values == model.source.exceptions_include
        assert model.matcher.exclude.values == model.source.exceptions
        assert model.matcher.group_by == model.group_by

    def test_parse_matcher_when_none(self, model: _XMLSmartPlaylist) -> None:
        model.group_by = "track"
        model.parse_matcher()
        assert model.group_by == _XMLSmartPlaylist.model_fields["group_by"].default

    def test_parse_matcher_with_no_group_by(self, model: _XMLSmartPlaylist) -> None:
        matcher = MatchFilter(group_by=None)
        model.parse_matcher(matcher)
        assert model.group_by == _XMLSmartPlaylist.model_fields["group_by"].default

    def test_parse_matcher(self, model: _XMLSmartPlaylist) -> None:
        matcher = MatchFilter(
            compare=ComparerFilter[LocalTrack](),
            include=PathsFilter(values={"a", "b", "c"}),
            exclude=PathsFilter(values={"1", "2", "3"}),
            group_by="album",
        )

        with mock.patch.object(_XMLSource, "parse_matcher") as mock_parse:
            model.parse_matcher(matcher)
            mock_parse.assert_called_once_with(matcher)
            assert model.group_by == matcher.group_by

    def test_build_sorter(self, model: _XMLSmartPlaylist, faker: Faker) -> None:
        model.shuffle_mode = "RecentAdded"
        model.shuffle_same_artist_weight = faker.random_int(-10, 10) / 10
        model.source.sort_by = _XMLDefinedSort(id=choice(tuple(_XMLDefinedSort.fields_map.keys())))

        assert model.sorter.sort_fields == model.source.sort_by.sort_fields
        assert model.sorter.shuffle_mode == ShuffleMode.RECENT_ADDED
        assert model.sorter.shuffle_weight == model.shuffle_same_artist_weight

    def test_parse_sorter_when_none(self, model: _XMLSmartPlaylist) -> None:
        model.parse_sorter()
        assert model.shuffle_mode == _XMLSmartPlaylist.model_fields["shuffle_mode"].default
        shuffle_same_artist_weight_default = _XMLSmartPlaylist.model_fields["shuffle_same_artist_weight"].default
        assert model.shuffle_same_artist_weight == shuffle_same_artist_weight_default

    def test_parse_sorter_with_no_options(self, model: _XMLSmartPlaylist) -> None:
        sorter = ItemSorter(sort_fields={"name": choice([True, False])})

        model.parse_sorter(sorter)
        assert model.shuffle_mode == _XMLSmartPlaylist.model_fields["shuffle_mode"].default
        assert model.shuffle_same_artist_weight == sorter.shuffle_weight

    def test_parse_sorter(self, model: _XMLSmartPlaylist, faker: Faker) -> None:
        sorter = ItemSorter(
            sort_fields={"name": choice([True, False])},
            shuffle_mode=ShuffleMode.RECENT_ADDED,
            shuffle_weight=faker.random_int(-10, 10) / 10,
        )

        with mock.patch.object(_XMLSource, "parse_sorter") as mock_parse:
            model.parse_sorter(sorter)
            mock_parse.assert_called_once_with(sorter)
            assert model.shuffle_mode == to_pascal(sorter.shuffle_mode.name)
            assert model.shuffle_same_artist_weight == sorter.shuffle_weight

    def test_parse_xml(self, adapter: TypeAdapter[_XMLSmartPlaylist], faker: Faker) -> None:
        xml = {
            "@SaveStaticCopy": choice([True, False]),
            "@LiveUpdating": choice([True, False]),
            "@Layout": faker.random_int(0, 10),
            "@LayoutGroupBy": faker.random_int(0, 10),
            "@ShuffleMode": to_pascal(choice([enum for enum in ShuffleMode]).name),
            "@ShuffleSameArtistWeight": faker.random_int(0, 10) / 10,
            "@GroupBy": choice(tuple(COMPARISON_FIELDS)),
            "@ConsolidateAlbums": choice([True, False]),
            "@MusicLibraryPath": faker.file_path(),
        }
        result = adapter.validate_python(xml).model_dump_xml()
        result.pop("Source")  # Source is tested separately
        assert result == xml


class TestXMLRoot(MusifyModelTester):
    @pytest.fixture
    def model(self) -> _XMLRoot:
        return _XMLRoot()

    @pytest.mark.skipif(not required_modules_installed(REQUIRED_MODULES), reason="xmltodict not installed")
    def test_parse_xml(self, adapter: TypeAdapter, xml_playlist: str):
        model = _XMLRoot.model_validate(xml_playlist)
        assert model.unparse_xml() == xml_playlist
