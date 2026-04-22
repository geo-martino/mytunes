from collections.abc import Generator
from copy import deepcopy
from unittest.mock import Mock, patch

import pytest
from faker import Faker
from pydantic import TypeAdapter
from pytest_mock import MockerFixture

from mytunes.core._collection.playlist import RemoteMutablePlaylist
from mytunes.core.properties.uri import URI
from mytunes.processors._flow import QuitImmediately
from mytunes.processors.check._playlist.match import InputMatch
from mytunes.processors.check._playlist.page import PlaylistsPage
from mytunes.processors.match import Matcher
from mytunes.result import LogFormatter
from processors.check.testers import InputMatchTester
from tests.processors.check._playlist.conftest import HasNameAndMutableURI, HasNameAndImmutableURI
from tests.remote import SimpleURI
from tests.testers import UniqueKeyTester
from tests.utils import split_list, patch_input


class TestInputMatch(InputMatchTester, UniqueKeyTester):
    @pytest.fixture
    def model(self, page: PlaylistsPage, playlist: RemoteMutablePlaylist, matcher: Matcher) -> InputMatch:
        return InputMatch(page=page, uri=playlist.uri, matcher=matcher)

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
            missing_items: list[HasNameAndMutableURI],
            mutable_items: list[HasNameAndMutableURI],
            mock_match_item_with_others: Mock,
            faker: Faker,
    ):
        item = faker.random_element(missing_items)

        matched, unmatched = split_list(mutable_items, 2)
        playlist.tracks.replace(mutable_items)

        match = deepcopy(item)
        match.uri = SimpleURI.create_random(kind=item.type)
        playlist.tracks.append(match)

        # should only try to match on items which haven't already been matched to items in the collection
        expected_items = unmatched + [match]

        assert model._match_item_with_playlist(item, others=matched)
        mock_match_item_with_others.assert_called_once_with(item, expected_items)

    def test_match_item_with_playlist_skips(
            self,
            model: InputMatch,
            playlist: RemoteMutablePlaylist,
            missing_items: list[HasNameAndMutableURI],
            mock_match_item_with_others: Mock,
            faker: Faker,
    ):
        item = faker.random_element(missing_items)
        assert not model._match_item_with_playlist(item, others=missing_items)
        mock_match_item_with_others.assert_called_once_with(item, playlist.tracks)

    ###########################################################################
    ## Match main
    ###########################################################################
    @pytest.fixture
    def mock_match_item_with_playlist(self, model: InputMatch, mocker: MockerFixture) -> Mock:
        return mocker.spy(model, '_match_item_with_playlist')

    async def test_match_skips_all(
            self,
            model: InputMatch,
            missing_items: list[HasNameAndMutableURI],
            mock_match_item_with_input: Mock,
            mock_match_item_with_playlist: Mock,
            mock_compare_uri_changes: Mock,
    ):
        with patch_input(iter(["na"])):
            result = await model.match(missing_items)

        assert not result.changed
        assert not result.unchanged
        assert not result.unavailable
        assert sorted(result.skipped) == sorted(missing_items)

        assert mock_match_item_with_input.call_count == len(missing_items)
        mock_match_item_with_playlist.assert_not_called()
        mock_compare_uri_changes.assert_called_once()

    async def test_match_marks_all_unavailable(
            self,
            model: InputMatch,
            missing_items: list[HasNameAndMutableURI],
            mock_match_item_with_input: Mock,
            mock_match_item_with_playlist: Mock,
            mock_compare_uri_changes: Mock,
    ):
        with patch_input(iter(["ua"])):
            result = await model.match(missing_items)

        assert not result.changed
        assert not result.unchanged
        assert sorted(result.unavailable) == sorted(missing_items)
        assert not result.skipped

        assert mock_match_item_with_input.call_count == len(missing_items)
        mock_match_item_with_playlist.assert_not_called()
        mock_compare_uri_changes.assert_called_once()

    async def test_match_with_playlist(
            self,
            model: InputMatch,
            missing_items: list[HasNameAndMutableURI],
            mock_match_item_with_input: Mock,
            mock_match_item_with_playlist: Mock,
            mock_compare_uri_changes: Mock,
    ):
        with patch_input(iter(["r", "r", "ra", "u", "n", "n", "s"])):
            result = await model.match(missing_items)

        assert not result.changed
        assert not result.unchanged
        assert len(result.unavailable) == 1
        assert len(result.skipped) == len(missing_items) - len(result.unavailable)

        # only tried the first few items, didn't match with playlist then skipped the rest
        assert mock_match_item_with_input.call_count == 3 + len(result.unavailable)
        assert mock_match_item_with_playlist.call_count == 3  # called for each input
        mock_compare_uri_changes.assert_called_once()
