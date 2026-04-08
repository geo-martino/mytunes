from copy import deepcopy
from unittest.mock import Mock, patch

import pytest
from faker import Faker
from pytest_mock import MockerFixture

from musify._models.collection.playlist import RemoteMutablePlaylist
from musify._models.properties.uri import HasURI, HasMutableURI, HasImmutableURI
from musify.processors.check._match.playlist import PlaylistMatch
from musify.processors.check._page import CheckerPage
from musify.processors.match import Matcher
from tests.processors.check.match.conftest import HasNameAndImmutableURI, HasNameAndMutableURI
from tests.testers import UniqueKeyTester
from tests.utils import split_list


class TestPlaylistMatch(UniqueKeyTester):
    @pytest.fixture
    def model(
            self,
            page: CheckerPage,
            playlist: RemoteMutablePlaylist,
            mutable_items: list[HasNameAndMutableURI],
            matcher: Matcher,
    ) -> PlaylistMatch:
        return PlaylistMatch(page=page, items=mutable_items, uri=playlist.uri, matcher=matcher)

    @pytest.fixture
    def mock_match_items_with_others(self, model: PlaylistMatch, mocker: MockerFixture) -> Mock:
        return mocker.spy(model, "_match_items_with_others")

    ###########################################################################
    ## Comparers
    ###########################################################################
    def test_compare_items(
            self,
            model: PlaylistMatch,
            mutable_items: list[HasMutableURI],
            unavailable_items: list[HasMutableURI],
            missing_items: list[HasMutableURI],
            mock_get_playlist_items: Mock,
            faker: Faker,
    ):
        initial, expected_added = split_list(mutable_items, 2)
        expected_unchanged, expected_removed = split_list(initial, 2)
        current = expected_unchanged + expected_added

        model.items = initial + unavailable_items + missing_items
        mock_get_playlist_items.return_value = current

        added, removed, unchanged, unavailable, missing = model._compare_items(current)

        assert added == expected_added
        assert removed == expected_removed
        assert unchanged == expected_unchanged
        assert unavailable == unavailable_items
        assert missing == missing_items

    def test_compare_duplicate_items(
            self,
            model: PlaylistMatch,
            available_items: list[HasURI],
            faker: Faker,
    ):
        initial_duplicates_count = faker.random_int(5, len(available_items))
        initial_duplicates = list(faker.random_elements(available_items, length=initial_duplicates_count))
        current_duplicates, removed_duplicates = split_list(initial_duplicates, 2)

        # check the test will actually be valid
        assert initial_duplicates
        assert current_duplicates
        assert removed_duplicates

        initial = available_items + initial_duplicates
        current, removed = split_list(available_items, 2)
        current += current_duplicates

        result = model._compare_duplicate_items(initial=initial, others=current, unique=removed)
        assert sorted(result, key=lambda x: id(x)) == sorted(removed_duplicates, key=lambda x: id(x))

    ###########################################################################
    ## Match helpers
    ###########################################################################
    def test_match_items_with_others(
            self,
            model: PlaylistMatch,
            mutable_items: list[HasMutableURI],
            mock_match: Mock,
            faker: Faker,
    ):
        items = deepcopy(mutable_items)
        others = deepcopy(list(faker.random_elements(items, unique=True)))

        expected_matches = items.index(sorted(others, key=lambda x: items.index(x))[-1]) + 1
        expected_updated = []
        expected_unchanged = []

        for item in items:
            match = any(item.uri == other.uri for other in others)
            expected_updated.append(item) if match else expected_unchanged.append(item)
            del item.uri

        assert all(item.has_uri for item in others)
        assert all(item.has_uri is None for item in items)

        changed = model._match_items_with_others(items=items, others=others)

        assert mock_match.call_count == expected_matches

        # should remove each item in others as it matches
        assert items == expected_unchanged != mutable_items
        assert not others
        assert changed == expected_updated

        for item in items:
            match = next(it for it in mutable_items if id(item) == id(item))
            if item in expected_updated:
                assert item.uri == match.uri
            else:
                assert item.uri is None

    def test_match_items_with_others_skips_immutable_items(
            self,
            model: PlaylistMatch,
            mutable_items: list[HasMutableURI],
            available_items: list[HasImmutableURI],
            mocker: MockerFixture,
    ):
        mock_match = mocker.spy(Matcher, "match")
        items = available_items + mutable_items
        expected_calls = len(mutable_items)

        model._match_items_with_others(items=items, others=mutable_items)
        assert mock_match.call_count == expected_calls

    ###########################################################################
    ## Match main
    ###########################################################################
    async def test_match_skips_on_no_changes(
            self,
            model: PlaylistMatch,
            playlist: RemoteMutablePlaylist,
            mutable_items: list[HasNameAndMutableURI],
            unavailable_items: list[HasNameAndMutableURI],
            mock_match_items_with_others: Mock,
    ):
        model.items = mutable_items + unavailable_items

        with patch.object(CheckerPage, "get_current_playlist_items", return_value=mutable_items):
            result = await model.match()

        assert not result.changed
        assert sorted(result.unchanged) == sorted(mutable_items)
        assert sorted(result.unavailable) == sorted(unavailable_items)
        assert not result.skipped

        mock_match_items_with_others.assert_not_called()

    async def test_match_skips_on_none_added(
            self,
            model: PlaylistMatch,
            mutable_items: list[HasNameAndMutableURI],
            unavailable_items: list[HasNameAndMutableURI],
            mock_get_playlist_items: Mock,
            mock_match_items_with_others: Mock,
            faker: Faker,
    ):
        unchanged, removed = split_list(mutable_items, 2)
        model.items = unchanged + removed + unavailable_items
        mock_get_playlist_items.return_value = unchanged

        result = await model.match()

        assert not result.changed
        assert sorted(result.unchanged) == sorted(unchanged)
        assert sorted(result.unavailable) == sorted(unavailable_items)
        assert sorted(result.skipped) == sorted(removed)

        mock_match_items_with_others.assert_not_called()

    async def test_match(
            self,
            model: PlaylistMatch,
            mutable_items: list[HasNameAndMutableURI],
            unavailable_items: list[HasNameAndImmutableURI],
            mock_get_playlist_items: Mock,
            mock_match_items_with_others: Mock,
            faker: Faker,
    ):
        unchanged, added, removed = split_list(mutable_items, 3)
        items = unchanged + removed + unavailable_items
        mock_get_playlist_items.return_value = unchanged + added

        for item in added:
            item = deepcopy(item)
            del item.uri
            items.append(item)

        model.items = items

        result = await model.match()

        assert sorted(result.changed) == sorted(added)
        assert sorted(result.unchanged) == sorted(unchanged)
        assert sorted(result.unavailable) == sorted(unavailable_items)
        assert sorted(result.skipped) == sorted(removed)

        mock_match_items_with_others.assert_called_once()
