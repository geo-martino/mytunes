from copy import deepcopy
from unittest.mock import Mock

import pytest
from faker import Faker
from pytest_mock import MockerFixture

from musify.models import ResourceModel
from musify.models.collection.playlist import RemoteMutablePlaylist
from musify.models.properties.uri import HasURI, HasMutableURI, HasImmutableURI
from musify.processors.check._match.playlist import PlaylistMatch
from musify.processors.check._page import CheckerPage
from musify.processors.match import Matcher
from tests.models.testers import BaseModelTester
from tests.processors.check.match.conftest import HasNameAndImmutableURI, HasNameAndMutableURI
from tests.processors.utils import MockCollection
from tests.utils import split_list


class TestPlaylistMatch(BaseModelTester):
    @pytest.fixture
    def model(self, page: CheckerPage, matcher: Matcher) -> PlaylistMatch:
        return PlaylistMatch(page=page, matcher=matcher)

    @pytest.fixture
    def mock_match_items_with_others(self, model: PlaylistMatch, mocker: MockerFixture) -> Mock:
        return mocker.spy(model, "_match_items_with_others")

    ###########################################################################
    ## Comparers
    ###########################################################################
    def test_compare_items(
            self,
            model: PlaylistMatch,
            collection: MockCollection,
            playlist: RemoteMutablePlaylist,
            available_items: list[HasURI],
            unavailable_items: list[HasURI],
            missing_items: list[HasURI],
            invalid_items: list[ResourceModel],
            mock_get_playlist_items: Mock,
            faker: Faker,
    ):
        initial, expected_added = split_list(available_items, 2)
        expected_unchanged, expected_removed = split_list(initial, 2)
        current = expected_unchanged + expected_added

        collection.all_items = initial + unavailable_items + missing_items + invalid_items
        mock_get_playlist_items.return_value = current

        added, removed, unchanged, unavailable, missing = model._compare_items(
            items=list(collection.items), others=current, uri=playlist.uri, name=playlist.name,
        )

        assert added == expected_added
        assert removed == expected_removed
        assert unchanged == expected_unchanged
        assert unavailable == unavailable_items
        assert missing == missing_items

    def test_compare_duplicate_items(
            self,
            model: PlaylistMatch,
            playlist: RemoteMutablePlaylist,
            collection: MockCollection,
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
        collection.all_items += initial_duplicates
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
        expected_calls = len(mutable_items)

        model._match_items_with_others(items=available_items + mutable_items, others=mutable_items)
        assert mock_match.call_count == expected_calls

    ###########################################################################
    ## Match main
    ###########################################################################
    async def test_match_skips_on_no_changes(
            self,
            model: PlaylistMatch,
            collection: MockCollection,
            playlist: RemoteMutablePlaylist,
            available_items: list[HasNameAndImmutableURI],
            unavailable_items: list[HasNameAndImmutableURI],
            invalid_items: list[ResourceModel],
            mock_match_items_with_others: Mock,
    ):
        collection.all_items = available_items + unavailable_items + invalid_items

        result = await model.match(items=list(collection.items), uri=playlist.uri, name=playlist.name)

        assert not result.changed
        assert sorted(result.unchanged) == sorted(available_items)
        assert sorted(result.unavailable) == sorted(unavailable_items)
        assert not result.skipped

        mock_match_items_with_others.assert_not_called()

    async def test_match_skips_on_none_added(
            self,
            model: PlaylistMatch,
            collection: MockCollection,
            playlist: RemoteMutablePlaylist,
            available_items: list[HasNameAndImmutableURI],
            unavailable_items: list[HasNameAndImmutableURI],
            invalid_items: list[ResourceModel],
            mock_get_playlist_items: Mock,
            mock_match_items_with_others: Mock,
            faker: Faker,
    ):
        unchanged, removed = split_list(available_items, 2)
        collection.all_items = unchanged + removed + unavailable_items + invalid_items
        mock_get_playlist_items.return_value = unchanged

        result = await model.match(items=list(collection.items), uri=playlist.uri, name=playlist.name)

        assert not result.changed
        assert sorted(result.unchanged) == sorted(unchanged)
        assert sorted(result.unavailable) == sorted(unavailable_items)
        assert sorted(result.skipped) == sorted(removed)

        mock_match_items_with_others.assert_not_called()

    async def test_match_skips_on_no_immutable_items(
            self,
            model: PlaylistMatch,
            collection: MockCollection,
            playlist: RemoteMutablePlaylist,
            available_items: list[HasNameAndImmutableURI],
            unavailable_items: list[HasNameAndImmutableURI],
            invalid_items: list[ResourceModel],
            mock_get_playlist_items: Mock,
            mock_match_items_with_others: Mock,
            faker: Faker,
    ):
        unchanged, added, removed = split_list(available_items, 3)
        collection.all_items = unchanged + removed + unavailable_items + invalid_items
        mock_get_playlist_items.return_value = unchanged + added

        result = await model.match(items=list(collection.items), uri=playlist.uri, name=playlist.name)

        assert not result.changed
        assert sorted(result.unchanged) == sorted(unchanged)
        assert sorted(result.unavailable) == sorted(unavailable_items)
        assert sorted(result.skipped) == sorted(removed)

        mock_match_items_with_others.assert_not_called()

    async def test_match(
            self,
            model: PlaylistMatch,
            collection: MockCollection,
            playlist: RemoteMutablePlaylist,
            mutable_items: list[HasNameAndMutableURI],
            unavailable_items: list[HasNameAndImmutableURI],
            invalid_items: list[ResourceModel],
            mock_get_playlist_items: Mock,
            mock_match_items_with_others: Mock,
            faker: Faker,
    ):
        unchanged, added, removed = split_list(mutable_items, 3)
        collection.all_items = unchanged + removed + unavailable_items + invalid_items
        mock_get_playlist_items.return_value = unchanged + added

        for item in added:
            item = deepcopy(item)
            del item.uri
            collection.all_items.append(item)

        result = await model.match(items=list(collection.items), uri=playlist.uri, name=playlist.name)

        assert sorted(result.changed) == sorted(added)
        assert sorted(result.unchanged) == sorted(unchanged)
        assert sorted(result.unavailable) == sorted(unavailable_items)
        assert sorted(result.skipped) == sorted(removed)

        mock_match_items_with_others.assert_called_once()
