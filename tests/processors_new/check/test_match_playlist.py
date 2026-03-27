from collections.abc import Collection
from copy import deepcopy
from typing import Generator, ClassVar
from unittest.mock import Mock, patch, AsyncMock

import pytest
from faker import Faker
from pytest_mock import MockerFixture

from musify.models import ResourceModel
from musify.models.api import RemoteAPI
from musify.models.api.playlist import PlaylistReadWriteEndpoints
from musify.models.collection import CollectionModel
from musify.models.collection.playlist import Playlist, RemoteMutablePlaylist
from musify.models.item.genre import Genre
from musify.models.item.track import Track
from musify.models.properties.name import HasName
from musify.models.properties.uri import HasURI, HasImmutableURI, HasMutableURI
from musify.processors_new.check import Checker, CheckResult
from musify.processors_new.match import Matcher
from tests.models.api.utils import MockUrlCursor
from tests.models.utils import MockRemoteCollection
from tests.utils import SimpleURI, split_list


class HasNameAndImmutableURI(HasName, HasImmutableURI):
    type: ClassVar[str] = Track.type
    name: str


class HasNameAndMutableURI(HasName, HasMutableURI):
    type: ClassVar[str] = Track.type
    name: str


class TestMatchWithPlaylist:
    @pytest.fixture
    def model(self, api: RemoteAPI) -> Checker:
        return Checker(api=api)

    @pytest.fixture(autouse=True)
    def playlist(self, model: Checker, playlist: RemoteMutablePlaylist) -> RemoteMutablePlaylist:
        model._playlists[playlist.uri] = playlist
        model._playlists_initial[playlist.uri] = deepcopy(playlist)
        return playlist

    @pytest.fixture(autouse=True)
    def collection(
            self,
            model: Checker,
            playlist: Playlist,
            available_items: list[HasURI],
            unavailable_items: list[HasURI],
            missing_items: list[HasURI],
            invalid_items: list[ResourceModel],
            faker: Faker,
    ) -> CollectionModel:
        collection = MockRemoteCollection(
            name=playlist.name,
            cursor=MockUrlCursor(url=faker.url()),
            uri=SimpleURI.create_random(MockRemoteCollection.type),
            items=available_items + unavailable_items + missing_items + invalid_items
        )
        model._collections[playlist.uri] = collection
        return collection

    @pytest.fixture
    def available_items(self, faker: Faker) -> list[HasImmutableURI]:
        return [
            HasNameAndImmutableURI(name=faker.name(), uri=SimpleURI.create_random(Track.type))
            for _ in range(faker.random_int(10, 30))
        ]

    @pytest.fixture
    def mutable_uri_items(self, faker: Faker) -> list[HasMutableURI]:
        return [
            HasNameAndMutableURI(name=faker.name(), uri=SimpleURI.create_random(Track.type))
            for _ in range(faker.random_int(10, 30))
        ]

    @pytest.fixture
    def unavailable_items(self, faker: Faker) -> list[HasImmutableURI]:
        return [
            HasNameAndImmutableURI(name=faker.name(), uri=SimpleURI.create_unavailable(Track.type))
            for _ in range(faker.random_int(5, 20))
        ]

    @pytest.fixture
    def missing_items(self, faker: Faker) -> list[HasImmutableURI]:
        missing = [
            HasNameAndImmutableURI(name=faker.name(), uri=None)
            for _ in range(faker.random_int(5, 20))
        ]

        for item in missing:
            item.__dict__["has_uri"] = None  # force missing URI

        return missing

    @pytest.fixture
    def invalid_items(self, faker: Faker) -> list[Genre]:
        return [Genre(name=faker.name()) for _ in range(faker.random_int(5, 20))]

    @pytest.fixture(autouse=True)
    def mock_get_playlist_items(self, available_items: list[HasURI], faker: Faker) -> Generator[Mock, None, None]:
        with patch.object(
                PlaylistReadWriteEndpoints, "get_all", return_value=available_items, new_callable=AsyncMock
        ) as mock_get_all:
            yield mock_get_all

    ###########################################################################
    ## Tests - getting playlist/collection items
    ###########################################################################
    def test_get_initial_playlist_items(
            self,
            model: Checker,
            playlist: RemoteMutablePlaylist,
            collection: CollectionModel,
            available_items: list[HasURI],
    ):
        result = model._get_initial_playlist_items(playlist)
        assert result == available_items

    async def test_get_current_playlist_items_removes_initial(
            self,
            model: Checker,
            playlist: RemoteMutablePlaylist,
            collection: CollectionModel,
            mock_get_playlist_items: Mock,
    ):
        initial_items, added_items = split_list(mock_get_playlist_items.return_value, 2)
        model._playlists_initial[playlist.uri].tracks.replace(initial_items)

        result = await model._get_current_playlist_items(playlist)

        assert result == added_items
        mock_get_playlist_items.assert_called_once_with(playlist.uri.api_url)

    def test_get_removed_duplicate_playlist_items(
            self,
            model: Checker,
            playlist: RemoteMutablePlaylist,
            collection: MockRemoteCollection,
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
        collection.items += initial_duplicates
        current, removed = split_list(available_items, 2)
        current += current_duplicates

        result = model._get_removed_duplicate_playlist_items(removed, initial, current)
        assert sorted(result, key=lambda x: id(x)) == sorted(removed_duplicates, key=lambda x: id(x))

    def test_get_missing_playlist_items(
            self,
            model: Checker,
            playlist: RemoteMutablePlaylist,
            missing_items: list[HasURI],
    ):
        result = model._get_missing_playlist_items(playlist)
        assert result == missing_items

    def test_get_invalid_collection_items(
            self,
            model: Checker,
            playlist: RemoteMutablePlaylist,
            unavailable_items: list[HasURI],
            invalid_items: list[ResourceModel],
    ):
        result = model._get_invalid_collection_items(playlist)
        assert result == unavailable_items + invalid_items

    ###########################################################################
    ## Tests - compare
    ###########################################################################
    async def test_compare_with_playlist(
            self,
            model: Checker,
            collection: MockRemoteCollection,
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

        collection.items = initial + unavailable_items + missing_items + invalid_items
        mock_get_playlist_items.return_value = current

        added, removed, unchanged, missing, invalid = await model._compare_with_playlist(playlist)

        assert added == expected_added
        assert removed == expected_removed
        assert unchanged == expected_unchanged
        assert missing == missing_items
        assert invalid == unavailable_items + invalid_items

    ###########################################################################
    ## Tests - match misc.
    ###########################################################################
    @pytest.fixture(autouse=True)
    def mock_match(self) -> Generator[Mock, None, None]:
        def _get_match[T: HasName | HasMutableURI](item: T, others: Collection[T], *_, **__) -> T | None:
            return next((other for other in others if item.name == other.name), None)

        with patch.object(Matcher, "match", side_effect=_get_match) as mock_match:
            yield mock_match

    def test_match_with_others(
            self,
            model: Checker,
            playlist: RemoteMutablePlaylist,
            mutable_uri_items: list[HasMutableURI],
            mock_match: Mock,
            faker: Faker,
    ):
        items = deepcopy(mutable_uri_items)
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

        changed = model._match_with_others(playlist, items=items, others=others)

        assert mock_match.call_count == expected_matches

        # should remove each item in others as it matches
        assert items == expected_unchanged != mutable_uri_items
        assert not others
        assert changed == expected_updated

        for item in items:
            match = next(it for it in mutable_uri_items if id(item) == id(item))
            if item in expected_updated:
                assert item.uri == match.uri
            else:
                assert item.uri is None

    def test_match_with_others_skips_immutable_items(
            self,
            model: Checker,
            playlist: RemoteMutablePlaylist,
            mutable_uri_items: list[HasMutableURI],
            available_items: list[HasImmutableURI],
            mocker: MockerFixture,
    ):
        mock_match = mocker.spy(Matcher, "match")
        expected_calls = len(mutable_uri_items)

        model._match_with_others(playlist, items=available_items + mutable_uri_items, others=mutable_uri_items)
        assert mock_match.call_count == expected_calls

    ###########################################################################
    ## Tests - match with playlist
    ###########################################################################
    @pytest.fixture
    def mock_match_with_others(self, model: Checker, mocker: MockerFixture) -> Mock:
        return mocker.spy(model, "_match_with_others")

    async def test_match_with_playlist_skips_on_no_changes(
            self,
            model: Checker,
            collection: MockRemoteCollection,
            playlist: RemoteMutablePlaylist,
            available_items: list[HasURI],
            unavailable_items: list[HasURI],
            invalid_items: list[ResourceModel],
            mock_match_with_others: Mock,
    ):
        collection.items = available_items + unavailable_items + invalid_items
        expected = CheckResult(unchanged=available_items, skipped=unavailable_items + invalid_items)

        result = await model._match_with_playlist(playlist)

        assert result == expected
        mock_match_with_others.assert_not_called()

    async def test_match_with_playlist_skips_on_none_added(
            self,
            model: Checker,
            collection: MockRemoteCollection,
            playlist: RemoteMutablePlaylist,
            available_items: list[HasURI],
            unavailable_items: list[HasURI],
            invalid_items: list[ResourceModel],
            mock_get_playlist_items: Mock,
            mock_match_with_others: Mock,
            faker: Faker,
    ):
        unchanged, removed = split_list(available_items, 2)
        collection.items = unchanged + removed + unavailable_items + invalid_items
        mock_get_playlist_items.return_value = unchanged

        expected = CheckResult(
            unchanged=unchanged,
            unavailable=removed,
            skipped=unavailable_items + invalid_items
        )

        result = await model._match_with_playlist(playlist)

        assert result == expected
        mock_match_with_others.assert_not_called()

    async def test_match_with_playlist_skips_on_no_immutable_items(
            self,
            model: Checker,
            collection: MockRemoteCollection,
            playlist: RemoteMutablePlaylist,
            available_items: list[HasURI],
            unavailable_items: list[HasURI],
            invalid_items: list[ResourceModel],
            mock_get_playlist_items: Mock,
            mock_match_with_others: Mock,
            faker: Faker,
    ):
        unchanged, added, removed = split_list(available_items, 3)
        collection.items = unchanged + removed + unavailable_items + invalid_items
        mock_get_playlist_items.return_value = unchanged + added

        expected = CheckResult(
            unchanged=unchanged,
            unavailable=removed,
            skipped=unavailable_items + invalid_items
        )

        result = await model._match_with_playlist(playlist)

        assert result == expected
        mock_match_with_others.assert_not_called()

    async def test_match_with_playlist(
            self,
            model: Checker,
            collection: MockRemoteCollection,
            playlist: RemoteMutablePlaylist,
            mutable_uri_items: list[HasMutableURI],
            unavailable_items: list[HasURI],
            invalid_items: list[ResourceModel],
            mock_get_playlist_items: Mock,
            mock_match_with_others: Mock,
            faker: Faker,
    ):
        unchanged, added, removed = split_list(mutable_uri_items, 3)
        collection.items = unchanged + removed + unavailable_items + invalid_items
        mock_get_playlist_items.return_value = unchanged + added

        for item in added:
            item = deepcopy(item)
            del item.uri
            collection.items.append(item)

        expected = CheckResult(
            changed=added,
            unchanged=unchanged,
            unavailable=removed,
            skipped=unavailable_items + invalid_items
        )

        result = await model._match_with_playlist(playlist)

        assert result == expected
        mock_match_with_others.assert_called_once()
