from abc import ABCMeta, abstractmethod
from collections.abc import Generator, Collection
from unittest.mock import Mock, patch, AsyncMock

import pytest
from faker import Faker

from musify.models import ResourceModel
from musify.models.api import RemoteAPI
from musify.models.api.search import SearchEndpoints
from musify.models.collection import CollectionModel, RemoteCollection
from musify.models.collection.album import AlbumCollection
from musify.models.item.album import Album
from musify.models.item.track import Track, RemoteTrack
from musify.models.properties.uri import HasImmutableURI, HasMutableURI
from musify.models.remote import RemoteResource
from musify.processors_new.match import Matcher
from musify.processors_new.match.score import NameScorer
from musify.processors_new.search import Searcher, SearchResult
from tests.models.api.utils import MockUrlCursor
from tests.models.testers import BaseModelTester
from tests.models.utils import MockRemoteCollection, MockRemoteResource
from tests.processors_new.utils import MockCollection
from tests.utils import SimpleURI, split_list


class SearcherTester(metaclass=ABCMeta):
    @pytest.fixture
    def model(self, api: RemoteAPI) -> Searcher:
        return Searcher(api=api)

    @abstractmethod
    def query_results(self, faker: Faker) -> list:
        raise NotImplementedError()

    @pytest.fixture
    def match[T](self, query_results: list[T], faker: Faker) -> T:
        return faker.random_element(query_results)

    @pytest.fixture
    def mock_query_item(self, query_results: list[RemoteResource]) -> Generator[Mock, None, None]:
        with patch.object(SearchEndpoints, "query_item", return_value=query_results) as mock_query_item:
            yield mock_query_item

    @pytest.fixture
    def mock_match(self, model: Searcher, match: RemoteTrack, faker: Faker) -> Generator[Mock, None, None]:
        with patch.object(Matcher, "match", return_value=match) as mock_match:
            yield mock_match

    @pytest.fixture
    def mock_match_item(self, model: Searcher, match: RemoteTrack, faker: Faker) -> Generator[Mock, None, None]:
        with patch.object(model, "_match_item", return_value=match) as mock_match:
            yield mock_match

    @pytest.fixture
    def mock_match_random_item(
            self, model: Searcher, faker: Faker
    ) -> Generator[tuple[Mock, list, list, list], None, None]:
        matches = []
        matched = []
        unmatched = []

        def _random_match[T: RemoteTrack](item: Track, results: list[T]) -> T | None:
            if faker.boolean():
                unmatched.append(item)
                return

            match = faker.random_element(results)
            matched.append(item)
            matches.append(match)
            return match

        with patch.object(model, "_match_item", side_effect=_random_match) as mock_match:
            yield mock_match, matches, matched, unmatched

    @staticmethod
    def assert_random_match_result(
            items: Collection,
            result: SearchResult,
            matches: Collection,
            matched: Collection,
            unmatched: Collection,
            skipped: Collection,
            mock_match_random_item: Mock,
    ):
        assert mock_match_random_item.call_count == len(items)
        assert len(matches) == len(matched)
        assert len(matched) + len(unmatched) == len(items)

        assert result == SearchResult(
            matches=matches,
            matched=matched,
            unmatched=unmatched,
            skipped=skipped,
        )


class TestSearcher(SearcherTester, BaseModelTester):
    @pytest.fixture
    def item(self, items: list[ResourceModel], faker: Faker) -> ResourceModel:
        return faker.random_element(items)

    @pytest.fixture
    def items(self, tracks: list[Track]) -> list[ResourceModel]:
        return tracks

    @pytest.fixture
    def query_results(self, faker: Faker) -> list[RemoteTrack]:
        return [
            RemoteTrack(
                name=faker.name(),
                uri=SimpleURI.from_id(faker.pystr(22, 22), kind=Track.type)
            )
            for _ in range(faker.random_int(5, 15))
        ]

    def test_skip_if_has_uri(self, model: Searcher, item: ResourceModel, match: RemoteResource):
        assert match.uri is not None

        model.skip_if_has_uri = False
        assert not model._should_skip(item)
        assert not model._should_skip(match)

        model.skip_if_has_uri = True
        assert not model._should_skip(item)
        assert model._should_skip(match)

    async def test_query(self, model: Searcher, item: ResourceModel, mock_query_item: Mock):
        model.skip_if_has_uri = False
        assert await model._query(item) == mock_query_item.return_value

    async def test_query_skips(self, model: Searcher, item: ResourceModel, mock_query_item: Mock, faker: Faker):
        with patch.object(model, "_should_skip", return_value=True):
            assert await model._query(item) is None
            mock_query_item.assert_not_called()

    async def test_query_returns_no_results(self, model: Searcher, item: ResourceModel, mock_query_item: Mock, faker: Faker):
        mock_query_item.return_value = []
        assert await model._query(item) is None

    def test_split_items(self, model: Searcher, items: list[ResourceModel], faker: Faker):
        expected_valid = []
        expected_invalid = []

        def _random_skip(item: ResourceModel) -> bool:
            if faker.boolean():
                expected_invalid.append(item)
                return True
            expected_valid.append(item)
            return False

        with patch.object(model, "_should_skip", side_effect=_random_skip):
            valid, invalid = model._split_items(items)
            assert valid == expected_valid
            assert invalid == expected_invalid

    def test_match_item_skips(self, model: Searcher, item: ResourceModel, query_results: list[RemoteTrack]):
        with (
            patch.object(model, "_pop_match_from_results", return_value=None),
            patch.object(model, "_assign_attributes_from_match") as mock_assign_attributes,
        ):
            assert model._match_item(item, query_results) is None
            mock_assign_attributes.assert_not_called()

    def test_match_item(self, model: Searcher, item: ResourceModel, query_results: list[RemoteTrack]):
        with (
            patch.object(model, "_pop_match_from_results", return_value=query_results[0]) as mock_match,
            patch.object(model, "_assign_attributes_from_match") as mock_assign_attributes,
        ):
            assert model._match_item(item, query_results) == mock_match.return_value
            mock_assign_attributes.assert_called_once_with(item, mock_match.return_value)

    def test_match_items(
            self,
            model: Searcher,
            items: list[ResourceModel],
            query_results: list[RemoteResource],
            mock_match_random_item: tuple[Mock, list, list, list],
            faker: Faker,
    ):
        mock_match_random_item, matches, matched, unmatched = mock_match_random_item

        valid = faker.random_elements(items)
        invalid = [item for item in items if item not in valid]

        assert model._match_items(items, [], skipped=invalid) == SearchResult(
            unmatched=items, skipped=invalid
        )

        result = model._match_items(valid, query_results, skipped=invalid)
        self.assert_random_match_result(
            items=valid,
            result=result,
            matches=matches,
            matched=matched,
            unmatched=unmatched,
            skipped=invalid,
            mock_match_random_item=mock_match_random_item,
        )

    @pytest.fixture
    def matcher(self, model: Searcher, faker: Faker) -> Matcher:
        scorers = [NameScorer()]
        matcher = Matcher(scorers=scorers)

        model.matcher = matcher
        return matcher

    def test_pop_match_from_results_skips(
            self,
            model: Searcher,
            item: ResourceModel,
            query_results: list[RemoteTrack],
            matcher: Matcher,
            mock_match: Mock,
    ):
        assert model._pop_match_from_results(item, None) is None
        mock_match.assert_not_called()

        assert model._pop_match_from_results(item, []) is None
        mock_match.assert_not_called()

        mock_match.return_value = None
        assert model._pop_match_from_results(item, query_results) is None
        mock_match.assert_called_once_with(item, query_results)

    def test_pop_match_from_results_no_matcher(
            self,
            model: Searcher,
            item: ResourceModel,
            query_results: list[RemoteTrack],
            matcher: Matcher,
            mock_match: Mock,
    ):
        model.matcher = None
        expected = query_results[0]

        assert model._pop_match_from_results(item, query_results) is expected
        mock_match.assert_not_called()
        assert expected not in query_results

    def test_pop_match_from_results_with_matcher(
            self,
            model: Searcher,
            item: ResourceModel,
            match: ResourceModel,
            query_results: list[RemoteTrack],
            matcher: Matcher,
            mock_match: Mock,
    ):
        assert model.matcher is not None
        assert match in query_results

        assert model._pop_match_from_results(item, query_results) is match
        mock_match.assert_called_once_with(item, query_results)
        assert match not in query_results

    def test_assign_attributes_from_match(self, model: Searcher, item: ResourceModel, match: RemoteTrack):
        model.assign_uri = False

        with (
            patch.object(model, "_assign_uri_from_match") as mock_assign_uri,
        ):
            model._assign_attributes_from_match(item, match)
            mock_assign_uri.assert_not_called()

            model.assign_uri = True
            model._assign_attributes_from_match(item, match)
            mock_assign_uri.assert_called_once_with(item, match)

    def test_assign_uri_from_match_skips(self, model: Searcher, item: ResourceModel, match: RemoteTrack):
        # nothing happens because item does not have a URI field
        assert not isinstance(item, HasImmutableURI) and not isinstance(item, HasMutableURI)
        model._assign_uri_from_match(item, match)

    def test_assign_uri_from_match(self, model: Searcher, query_results: list[RemoteTrack], match: RemoteTrack):
        item = next(result for result in query_results if result is not match)

        assert item.uri != match.uri
        model._assign_uri_from_match(item, match)
        assert item.uri == match.uri


class TestItemSearcher(SearcherTester):
    """Test item search functionality only"""
    @pytest.fixture
    def items(self, tracks: list[Track]) -> list[Track]:
        return tracks[:len(tracks) // 2]

    @pytest.fixture
    def query_results(self, faker: Faker) -> list[RemoteTrack]:
        return [
            RemoteTrack(
                name=faker.name(),
                uri=SimpleURI.from_id(faker.pystr(22, 22), kind=Track.type)
            )
            for _ in range(faker.random_int(5, 15))
        ]

    async def test_search_item(
            self, model: Searcher, items: list[Track], mock_query_item: Mock, mock_match_item: Mock
    ):
        item = items[0]

        assert await model.search_item(item) is mock_match_item.return_value
        mock_query_item.assert_called_once_with(item)
        mock_match_item.assert_called_once_with(item, mock_query_item.return_value)

    async def test_search_items(
            self,
            model: Searcher,
            items: list[Track],
            query_results: list[RemoteTrack],
            mock_query_item: Mock,
            mock_match_random_item: tuple[Mock, list[RemoteTrack], list[Track], list[Track]],
            faker: Faker,
    ):
        mock_match_random_item, matches, matched, unmatched = mock_match_random_item
        valid = faker.random_elements(items)
        invalid = [item for item in items if item not in valid]

        with patch.object(model, "_split_items", return_value=(valid, invalid)) as mock_split_items:
            result = await model.search_items(items)

            mock_split_items.assert_called_once_with(items)
            assert mock_query_item.call_count == len(valid)

            self.assert_random_match_result(
                items=valid,
                result=result,
                matches=matches,
                matched=matched,
                unmatched=unmatched,
                skipped=invalid,
                mock_match_random_item=mock_match_random_item,
            )

    async def test_search_from_result(
            self,
            model: Searcher,
            items: list[Track],
            query_results: list[RemoteTrack],
            mock_query_item: Mock,
            mock_match_random_item: tuple[Mock, list[RemoteTrack], list[Track], list[Track]],
            faker: Faker,
    ):
        mock_match_random_item, matches, matched, unmatched = mock_match_random_item

        items_matched, items_unmatched, _ = split_list(items, 2)
        items_matches = faker.random_elements(query_results, length=len(items_matched))

        valid = faker.random_elements(items_unmatched)
        invalid = [item for item in items if item not in valid]

        result_to_search = SearchResult(
            matches=items_matches, matched=items_matched, unmatched=valid, skipped=invalid
        )
        result = await model._search_from_result(result_to_search, items)

        assert mock_query_item.call_count == len(valid)

        self.assert_random_match_result(
            items=valid,
            result=result,
            matches=matches,
            matched=matched,
            unmatched=unmatched,
            skipped=invalid,
            mock_match_random_item=mock_match_random_item,
        )


class TestCollectionSearcher(SearcherTester):
    """Test collection search functionality only"""
    @pytest.fixture
    def collection(self, collections: list[CollectionModel], faker: Faker) -> CollectionModel:
        return faker.random_element(collections)

    @pytest.fixture
    def collections(self, albums: list[Album], tracks: list[Track], faker: Faker) -> list[CollectionModel]:
        return [
            MockCollection(name=album.name, items=faker.random_elements(tracks))
            for album in albums
        ]

    @pytest.fixture
    def query_results(self, faker: Faker) -> list[RemoteCollection]:
        return [
            MockRemoteCollection(
                name=faker.name(),
                uri=SimpleURI.from_id(faker.pystr(22, 22), kind=MockRemoteCollection.type),
                cursor=MockUrlCursor(url=faker.url()),
            )
            for _ in range(faker.random_int(5, 15))
        ]

    @pytest.fixture
    def mock_match_item(self, model: Searcher, match: RemoteCollection, faker: Faker) -> Generator[Mock, None, None]:
        with patch.object(model, "_match_item", return_value=match) as mock_match:
            yield mock_match

    @patch.multiple(
        CollectionModel,
        __abstractmethods__=set(),
        _items=Mock(),
    )
    def test_collection_on_items_only(self, model: Searcher, collection: CollectionModel, faker: Faker) -> None:
        assert isinstance(collection, ResourceModel) and isinstance(collection, CollectionModel)
        assert not model._should_search_on_items_only(collection)
        assert model._should_search_on_items_only(CollectionModel())  # not a resource model

        # always returns True now
        model.items_only_on_collections = True
        assert model._should_search_on_items_only(collection)

    @patch.multiple(
        AlbumCollection,
        __abstractmethods__=set(),
        _items=Mock(),
    )
    def test_album_on_items_only(self, model: Searcher, tracks: list[Track], faker: Faker) -> None:
        album = Album(name=faker.sentence(), compilation=False)
        for track in tracks:
            track.album = album

        model.compilation_albums_as_tracks_only = False

        collection = AlbumCollection(**album.model_dump(), tracks=tracks)
        assert not model._should_search_on_items_only(collection)

        collection.compilation = True
        assert not model._should_search_on_items_only(collection)

        model.compilation_albums_as_tracks_only = True
        assert model._should_search_on_items_only(collection)

    async def test_extend_collection_with_reload(self, model: Searcher, match: RemoteCollection, faker: Faker):
        item = MockRemoteResource.model_validate(match.model_dump())
        with (
            patch.object(item.__class__, "reload", return_value=match, new_callable=AsyncMock) as mock_reload,
            patch.object(match.__class__, "extend", new_callable=AsyncMock) as mock_extend,
        ):
            assert await model._extend_collection_items(item) is match

            mock_reload.assert_called_once_with(model.api)
            mock_extend.assert_called_once_with(model.api)

    async def test_extend_collection_without_reload(self, model: Searcher, match: RemoteCollection, faker: Faker):
        with (
            patch.object(match.__class__, "reload", return_value=match, new_callable=AsyncMock) as mock_reload,
            patch.object(match.__class__, "extend", new_callable=AsyncMock) as mock_extend,
        ):
            assert await model._extend_collection_items(match) is match

            mock_reload.assert_not_called()
            mock_extend.assert_called_once_with(model.api)

    async def test_search_collections(self, model: Searcher, collections: list[CollectionModel], faker: Faker):
        def _random_result(*_, **__) -> tuple[str, SearchResult]:
            return faker.sentence(), SearchResult()

        with patch.object(
                model, "_search_collection", side_effect=_random_result
        ) as mock_search_collection:
            results = await model.search_collections(collections)

            assert len(results) == len(collections)
            assert mock_search_collection.call_count == len(collections)
            for call in mock_search_collection.call_args_list:
                assert call.kwargs["show_bar"] is False

    @pytest.fixture
    def mock_search_items_only(self, model: Searcher) -> Generator[Mock, None, None]:
        with patch.object(model, "_should_search_on_items_only", return_value=False) as mock_items_only:
            yield mock_items_only

    @pytest.fixture
    def mock_search_items(self, model: Searcher) -> Generator[Mock, None, None]:
        with patch.object(model, "_search_items", return_value=SearchResult()) as mock_search_items:
            yield mock_search_items

    @pytest.fixture
    def mock_search_from_result(self, model: Searcher) -> Generator[Mock, None, None]:
        with patch.object(model, "_search_from_result", return_value=SearchResult()) as mock_search_from_result:
            yield mock_search_from_result

    @pytest.fixture
    def mock_match_items(self, model: Searcher, match: RemoteCollection) -> Generator[Mock, None, None]:
        with patch.object(model, "_match_items", return_value=SearchResult()) as mock_match:
            yield mock_match

    @pytest.fixture
    def mock_extend(self, model: Searcher) -> Generator[Mock, None, None]:
        with patch.object(
                model, "_extend_collection_items", side_effect=lambda x: x, new_callable=AsyncMock
        ) as mock_extend:
            yield mock_extend

    async def test_search_collection_on_items_only(
            self,
            model: Searcher,
            collection: CollectionModel,
            mock_search_items_only: Mock,
            mock_query_item: Mock,
            mock_match_item: Mock,
            mock_search_items: Mock,
            mock_match_items: Mock,
            mock_extend: Mock,
            mock_search_from_result: Mock,
    ):
        mock_search_items_only.return_value = True
        await model.search_collection(collection)

        mock_query_item.assert_not_called()
        mock_match_item.assert_not_called()
        mock_search_items.assert_called_once()
        mock_match_items.assert_not_called()
        mock_extend.assert_not_called()
        mock_search_from_result.assert_not_called()

    async def test_search_collection_not_found(
            self,
            model: Searcher,
            collection: CollectionModel,
            mock_search_items_only: Mock,
            mock_query_item: Mock,
            mock_match_item: Mock,
            mock_search_items: Mock,
            mock_match_items: Mock,
            mock_extend: Mock,
            mock_search_from_result: Mock,
    ):
        mock_search_items_only.return_value = False
        mock_match_item.return_value = None
        await model.search_collection(collection)

        mock_query_item.assert_called_once()
        mock_match_item.assert_called_once()
        mock_search_items.assert_called_once()
        mock_match_items.assert_not_called()
        mock_extend.assert_called_once()
        mock_search_from_result.assert_not_called()

    async def test_search_collection_found(
            self,
            model: Searcher,
            collection: CollectionModel,
            match: RemoteCollection,
            mock_search_items_only: Mock,
            mock_query_item: Mock,
            mock_match_item: Mock,
            mock_search_items: Mock,
            mock_match_items: Mock,
            mock_extend: Mock,
            mock_search_from_result: Mock,
    ):
        mock_search_items_only.return_value = False
        mock_match_item.return_value = match
        await model.search_collection(collection)

        mock_query_item.assert_called_once()
        mock_match_item.assert_called_once()
        mock_search_items.assert_not_called()
        mock_match_items.assert_called_once()
        mock_extend.assert_called_once()
        mock_search_from_result.assert_not_called()

    async def test_search_collection_keeps_searching_for_items(
            self,
            model: Searcher,
            collection: CollectionModel,
            tracks: list[Track],
            match: RemoteCollection,
            mock_search_items_only: Mock,
            mock_query_item: Mock,
            mock_match_item: Mock,
            mock_search_items: Mock,
            mock_match_items: Mock,
            mock_extend: Mock,
            mock_search_from_result: Mock,
    ):
        mock_search_items_only.return_value = False
        mock_match_item.return_value = match

        mock_match_items.return_value = SearchResult(unmatched=tracks)
        model.keep_matching_collection_items = True

        await model.search_collection(collection)

        mock_query_item.assert_called_once()
        mock_match_item.assert_called_once()
        mock_search_items.assert_not_called()
        mock_match_items.assert_called_once()
        mock_extend.assert_called_once()
        mock_search_from_result.assert_called_once()
