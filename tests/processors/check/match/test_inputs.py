from collections.abc import Generator
from copy import deepcopy
from unittest.mock import Mock, patch

import pytest
from faker import Faker
from pydantic import TypeAdapter
from pytest_mock import MockerFixture

from mytunes._models.collection.playlist import RemoteMutablePlaylist
from mytunes._models.properties.uri import URI
from mytunes._models.result import LogFormatter
from mytunes.processors._flow import QuitImmediately
from mytunes.processors.check._match.inputs import InputMatch
from mytunes.processors.check._page import CheckerPage
from mytunes.processors.match import Matcher
from tests.processors.check.match.conftest import HasNameAndMutableURI, HasNameAndImmutableURI
from tests.remote import SimpleURI
from tests.testers import UniqueKeyTester
from tests.utils import split_list, patch_input


class TestInputMatch(UniqueKeyTester):
    @pytest.fixture
    def model(
            self,
            page: CheckerPage,
            playlist: RemoteMutablePlaylist,
            missing_items: list[HasNameAndMutableURI],
            matcher: Matcher,
    ) -> InputMatch:
        return InputMatch(page=page, items=missing_items, uri=playlist.uri, matcher=matcher)

    @pytest.fixture(autouse=True)
    def mock_uri_adapter(self) -> Generator[Mock]:
        adapter = TypeAdapter(SimpleURI)
        with patch.object(URI, "get_adapter_for_source", return_value=adapter) as mock_adapter:
            yield mock_adapter

    ###########################################################################
    ## Utilities
    ###########################################################################
    def test_configure_formatter_for_items(
            self, model: InputMatch, available_items: list[HasNameAndImmutableURI], faker: Faker
    ):
        width = max(len(item.name) for item in available_items)
        InputMatch.input_formatter = LogFormatter(
            width=faker.random_int(),
            max_width=None,
        )

        formatter = model._configure_formatter_for_items(available_items)
        assert formatter.width == width

        width = max(width - faker.random_int(1, width), 3)
        InputMatch.input_formatter = LogFormatter(
            width=faker.random_int(),
            max_width=width,
        )
        formatter = model._configure_formatter_for_items(available_items)
        assert formatter.width == width

    ###########################################################################
    ## Comparers
    ###########################################################################
    def test_compare_uri_changes(self, model: InputMatch, mutable_items: list[HasNameAndMutableURI], faker: Faker):
        initial = mutable_items

        for change in faker.random_elements(initial, unique=True):
            if faker.boolean():
                change.uri = SimpleURI.create_unavailable(kind=change.type)
            else:
                del change.uri

        changed = []
        unchanged = []
        unavailable = []
        skipped = []

        changes = deepcopy(mutable_items)
        for change in changes:
            if change.has_uri is not None:
                unchanged.append(change)
                continue

            if faker.boolean():
                change.uri = SimpleURI.create_random(kind=change.type)
                changed.append(change)
                assert change.has_uri is True
            elif faker.boolean():
                change.uri = SimpleURI.create_unavailable(kind=change.type)
                unavailable.append(change)
                assert change.has_uri is False
            else:
                skipped.append(change)
                assert change.has_uri is None

        result = model._compare_uri_changes(initial, changes)

        assert sorted(result.changed) == sorted(changed)
        assert sorted(result.unchanged) == sorted(unchanged)
        assert sorted(result.unavailable) == sorted(unavailable)
        assert sorted(result.skipped) == sorted(skipped)

    ###########################################################################
    ## Match helpers
    ###########################################################################
    @pytest.fixture
    def mock_match_item_with_others(self, model: InputMatch, mocker: MockerFixture) -> Mock:
        return mocker.spy(model, '_match_item_with_others')

    def test_match_item_with_playlist(
            self,
            model: InputMatch,
            playlist: RemoteMutablePlaylist,
            mutable_items: list[HasNameAndMutableURI],
            mock_match_item_with_others: Mock,
            faker: Faker,
    ):
        item = faker.random_element(model.items)

        matched, unmatched = split_list(mutable_items, 2)
        model.items = matched
        playlist.tracks.replace(mutable_items)

        match = deepcopy(item)
        match.uri = SimpleURI.create_random(kind=item.type)
        playlist.tracks.append(match)

        # should only try to match on items which haven't already been matched to items in the collection
        expected_items = unmatched + [match]

        assert model._match_item_with_playlist(item)
        mock_match_item_with_others.assert_called_once_with(item, expected_items, "INPUT")

    def test_match_item_with_playlist_skips(
            self,
            model: InputMatch,
            playlist: RemoteMutablePlaylist,
            mock_match_item_with_others: Mock,
            faker: Faker,
    ):
        item = faker.random_element(model.items)
        assert not model._match_item_with_playlist(item)
        mock_match_item_with_others.assert_called_once_with(item, playlist.tracks, "INPUT")

    ###########################################################################
    ## Match main
    ###########################################################################
    @pytest.fixture
    def mock_match_item_with_input(self, model: InputMatch, mocker: MockerFixture) -> Mock:
        return mocker.spy(model, '_match_item_with_input')

    @pytest.fixture
    def mock_match_item_with_playlist(self, model: InputMatch, mocker: MockerFixture) -> Mock:
        return mocker.spy(model, '_match_item_with_playlist')

    @pytest.fixture
    def mock_compare_uri_changes(self, model: InputMatch, mocker: MockerFixture) -> Mock:
        return mocker.spy(model, '_compare_uri_changes')

    async def test_match_skips_on_no_missing_items(
            self,
            model: InputMatch,
            mutable_items: list[HasNameAndMutableURI],
            mock_match_item_with_input: Mock,
            mock_match_item_with_playlist: Mock,
            mock_compare_uri_changes: Mock,
            faker: Faker,
    ):
        model.items = mutable_items
        result = await model.match()

        assert not result.changed
        assert not result.unchanged
        assert not result.unavailable
        assert not result.skipped

        mock_match_item_with_input.assert_not_called()
        mock_match_item_with_playlist.assert_not_called()
        mock_compare_uri_changes.assert_not_called()

    async def test_match_skips(
            self,
            model: InputMatch,
            mock_match_item_with_input: Mock,
            mock_match_item_with_playlist: Mock,
            mock_compare_uri_changes: Mock,
    ):
        kind = model.items[0].type
        inputs = [
            SimpleURI.create_random(kind),
            "h",
            SimpleURI.create_random(kind),
            "s",
        ]

        with patch_input(iter(inputs)):
            result = await model.match()

        assert len(result.changed) == 2
        assert not result.unchanged
        assert not result.unavailable
        assert len(result.skipped) == len(model.items) - len(result.changed)

        assert mock_match_item_with_input.call_count == 3  # quits early
        mock_match_item_with_playlist.assert_not_called()
        mock_compare_uri_changes.assert_called_once()

    async def test_match_quits(
            self,
            model: InputMatch,
            mock_match_item_with_input: Mock,
            mock_match_item_with_playlist: Mock,
            mock_compare_uri_changes: Mock,
    ):
        kind = model.items[0].type
        inputs = [
            SimpleURI.create_random(kind),
            "h",
            SimpleURI.create_random(kind),
            "q",
        ]

        with patch_input(iter(inputs)), pytest.raises(QuitImmediately):
            await model.match()

        assert mock_match_item_with_input.call_count == 3  # quits early
        mock_match_item_with_playlist.assert_not_called()
        mock_compare_uri_changes.assert_not_called()  # doesn't produce a result

    async def test_match_assigns_uris(
            self,
            model: InputMatch,
            mock_match_item_with_input: Mock,
            mock_match_item_with_playlist: Mock,
            mock_compare_uri_changes: Mock,
    ):
        uris = [SimpleURI.create_random(kind=item.type) for item in model.items]
        with patch_input(iter(uris)):
            result = await model.match()

        assert sorted(result.changed) == sorted(model.items)
        assert not result.unchanged
        assert not result.unavailable
        assert not result.skipped

        assert mock_match_item_with_input.call_count == len(model.items)
        mock_match_item_with_playlist.assert_not_called()
        mock_compare_uri_changes.assert_called_once()

    async def test_match_skips_all(
            self,
            model: InputMatch,
            mock_match_item_with_input: Mock,
            mock_match_item_with_playlist: Mock,
            mock_compare_uri_changes: Mock,
    ):
        with patch_input(iter(["na"])):
            result = await model.match()

        assert not result.changed
        assert not result.unchanged
        assert not result.unavailable
        assert sorted(result.skipped) == sorted(model.items)

        assert mock_match_item_with_input.call_count == len(model.items)
        mock_match_item_with_playlist.assert_not_called()
        mock_compare_uri_changes.assert_called_once()

    async def test_match_marks_all_unavailable(
            self,
            model: InputMatch,
            mock_match_item_with_input: Mock,
            mock_match_item_with_playlist: Mock,
            mock_compare_uri_changes: Mock,
    ):
        with patch_input(iter(["ua"])):
            result = await model.match()

        assert not result.changed
        assert not result.unchanged
        assert sorted(result.unavailable) == sorted(model.items)
        assert not result.skipped

        assert mock_match_item_with_input.call_count == len(model.items)
        mock_match_item_with_playlist.assert_not_called()
        mock_compare_uri_changes.assert_called_once()

    async def test_match_with_playlist(
            self,
            model: InputMatch,
            mock_match_item_with_input: Mock,
            mock_match_item_with_playlist: Mock,
            mock_compare_uri_changes: Mock,
    ):
        with patch_input(iter(["r", "r", "ra", "u", "n", "n", "s"])):
            result = await model.match()

        assert not result.changed
        assert not result.unchanged
        assert len(result.unavailable) == 1
        assert len(result.skipped) == len(model.items) - len(result.unavailable)

        # only tried the first few items, didn't match with playlist then skipped the rest
        assert mock_match_item_with_input.call_count == 3 + len(result.unavailable)
        assert mock_match_item_with_playlist.call_count == 3  # called for each input
        mock_compare_uri_changes.assert_called_once()

    async def test_match_complex_assignment(
            self,
            model: InputMatch,
            mock_match_item_with_input: Mock,
            mock_match_item_with_playlist: Mock,
            mock_compare_uri_changes: Mock,
    ):
        kind = model.items[0].type
        inputs = [
            "h",
            "invalid_input",
            "",
            "n",
            SimpleURI.create_random(kind),
            "h",
            "u",
            SimpleURI.create_unavailable(kind),
            "n",
            "h",
            "invalid_input",
            "n",
            SimpleURI.create_unavailable(kind),
            "invalid_input",
            SimpleURI.create_random(kind),
            "na",
        ]

        with patch_input(iter(inputs)):
            result = await model.match()

        assert len(result.changed) == 2
        assert not result.unchanged
        assert len(result.unavailable) == 3
        assert len(result.skipped) == len(model.items) - len(result.changed) - len(result.unavailable)

        assert mock_match_item_with_input.call_count == len(model.items)
        mock_match_item_with_playlist.assert_not_called()
        mock_compare_uri_changes.assert_called_once()

