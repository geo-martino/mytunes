import math
from collections.abc import Callable, Generator, Sequence
from copy import deepcopy
from typing import Any, final
from unittest import mock
from unittest.mock import patch, Mock, AsyncMock, PropertyMock

import pytest
from aiorequestful.request import RequestHandler
from faker import Faker
from pydantic import AliasPath, TypeAdapter
from pytest_mock import MockerFixture
from yarl import URL

from musify.exception import MusifyTypeError
from musify.models.api import Endpoints, ReadItemEndpoints, ReadItemsEndpoints, \
    ReadSavedEndpoints, WriteCollectionEndpoints, WriteSavedEndpoints, ReadCollectionEndpoints
from musify.models.collection import RemoteCollection
from musify.models.cursors import PageCursor, IndexCursor, UrlCursor
from musify.models.exception import APIModelError
from musify.models.item.album import RemoteAlbum
from musify.models.item.artist import RemoteArtist
from musify.models.item.track import RemoteTrack
from musify.models.properties.uri import URI
from tests.models.api.testers import EndpointsTester, URI_TYPE_CONVERTERS
from tests.models.api.utils import MockIndexCursor, MockUrlCursor, MockKeyCursor, MockInitialCursor
from tests.models.utils import MockRemoteResource, MockRemoteCollection
from tests.utils import SimpleURI


class TestCreateFromResponse:
    @final
    class MockEndpoints(Endpoints[SimpleURI, MockRemoteResource]):
        __final__ = True
        source = MockRemoteResource.source
        type = MockRemoteResource.type

    @final
    class MockRemoteTrack(RemoteTrack, MockRemoteResource):
        __final__ = True

    @final
    class MockRemoteArtist(RemoteArtist, MockRemoteResource):
        __final__ = True

    @final
    class MockRemoteAlbum(RemoteAlbum, MockRemoteResource):
        __final__ = True

    def test_create_fails_on_non_final_class(self):
        with pytest.raises(APIModelError, match="Can only create resources from final API models"):
            Endpoints.create_model({})

    def test_create_fails_on_unmatched_source(self):
        @final
        class MockEndpointsTest(Endpoints[SimpleURI, MockRemoteResource]):
            __final__ = True
            source = "unknown_source"
            type = MockRemoteResource.type

        with pytest.raises(APIModelError, match="No registered resource models found"):
            MockEndpointsTest.create_model({})

    def test_create_fails_on_unmatched_kind(self):
        @final
        class MockEndpointsTest(Endpoints[SimpleURI, MockRemoteResource]):
            __final__ = True
            source = MockRemoteResource.source
            type = "unknown_type"

        with pytest.raises(APIModelError, match=f"Could not find a registered {MockRemoteResource.source!r} model"):
            MockEndpointsTest.create_model({})

    def test_creates_current_kind(self, faker: Faker):
        uri = SimpleURI.from_id(faker.random_int(1, 100), kind=self.MockEndpoints.type)

        result = self.MockEndpoints.create_model(dict(name=faker.word(), uri=uri))
        assert isinstance(result, MockRemoteResource)
        assert result.type == self.MockEndpoints.type

    def test_creates_given_kind(self, faker: Faker):
        types = [
            RemoteTrack.type,
            RemoteAlbum.type,
            RemoteArtist.type,
        ]
        types.remove(self.MockEndpoints.type)
        expected_type = faker.random_element(types)

        uri = SimpleURI.from_id(faker.random_int(1, 100), kind=expected_type)

        result = self.MockEndpoints.create_model(dict(name=faker.word(), uri=uri), kind=expected_type)
        assert isinstance(result, MockRemoteResource)
        assert result.type != self.MockEndpoints.type
        assert result.type == expected_type


class TestEndpoints(EndpointsTester):
    @pytest.fixture
    def model(self, handler: RequestHandler) -> Endpoints:
        return Endpoints[SimpleURI, MockRemoteResource](
            handler=handler,
        )

    @pytest.fixture
    def cursor(
            self,
            index_cursors: list[IndexCursor],
            url_cursors: list[UrlCursor],
            total: int,
            uri: URI,
            faker: Faker
    ) -> PageCursor:
        key_cursor = MockKeyCursor(
            url=uri.api_url,
            before=faker.pystr(22, 22),
            after=faker.pystr(22, 22),
            total=total,
        )
        return faker.random_element([
            index_cursors[0],
            key_cursor,
            url_cursors[0],
            MockInitialCursor(url=uri.api_url, total=total),
        ])

    @pytest.fixture
    def index_cursors(self, uri: URI, total: int, faker: Faker) -> list[IndexCursor]:
        # at least 3 pages to properly test pagination and generation
        limit = faker.random_int(1, 20)
        offset = max(0, total - faker.random_int(limit * 3, total))

        initial_cursor = MockIndexCursor(url=uri.api_url, limit=limit, offset=offset, total=total)
        cursors = list(initial_cursor.iter_pages)

        assert len(set(cursor.offset for cursor in cursors)) == len(cursors)
        assert len(set(cursor.url for cursor in cursors)) == len(cursors)
        assert cursors[-1].offset + cursors[-1].limit > initial_cursor.total
        assert cursors[-2].offset + cursors[-2].limit <= initial_cursor.total
        assert cursors[-1].next is None

        return cursors

    @pytest.fixture
    def url_cursors(self, index_cursors: list[IndexCursor]) -> list[UrlCursor]:
        return [
            MockUrlCursor(
                url=cursor.url,
                previous=cursor.previous.url if cursor.previous else None,
                next=cursor.next.url if cursor.next else None,
                total=cursor.total,
            )
            for cursor in index_cursors
        ]

    @pytest.fixture
    def expected_urls(self, index_cursors: list[IndexCursor]) -> list[URL]:
        return [cursor.next.url for cursor in index_cursors if cursor.next]

    @pytest.fixture
    def expected_items(self, items: list[dict[str, Any]], index_cursors: list[IndexCursor]) -> list[dict[str, Any]]:
        initial_cursor = index_cursors[0]
        return items[initial_cursor.next.offset:]

    @pytest.fixture
    def mock_index_pages(
            self,
            index_cursors: list[IndexCursor],
            items: list[dict[str, Any]],
            total: int,
            items_key: str,
    ) -> Generator[Mock, None, None]:
        cursors = {cursor.url: cursor for cursor in index_cursors}

        def _return_response(url: URL, *_, **__) -> dict[str, Any]:
            cursor = cursors[url]
            page_items = items[cursor.offset:cursor.offset + cursor.limit]
            return cursor.model_dump() | {items_key: page_items}

        with patch.object(RequestHandler, "get", side_effect=_return_response, new_callable=AsyncMock) as mock_get:
            yield mock_get

    @pytest.fixture
    def mock_url_pages(
            self,
            index_cursors: list[IndexCursor],
            url_cursors: list[UrlCursor],
            items: list[dict[str, Any]],
            total: int,
    ) -> Generator[Mock, None, None]:
        cursors = {cursor.url: cursor for cursor in url_cursors}
        index_cursors = {cursor.url: cursor for cursor in index_cursors}

        def _return_response(url: URL, *_, **__) -> dict[str, Any]:
            url_cursor = cursors[url]
            index_cursor = index_cursors[url]
            page_items = items[index_cursor.offset:index_cursor.offset + index_cursor.limit]
            return url_cursor.model_dump() | {"items": page_items}

        with (
            patch.object(RequestHandler, "get", side_effect=_return_response, new_callable=AsyncMock) as mock_get,
            # force validating response as UrlCursor, otherwise it will be validated as IndexCursor
            patch.object(
                PageCursor,
                "get_cursor_from_response",
                side_effect=lambda response, *_, **__: MockUrlCursor.model_validate(response)
            )
        ):
            yield mock_get

    @pytest.fixture
    def mock_pagination(self, model: Endpoints, mocker: MockerFixture) -> Mock:
        return mocker.spy(model, "_get_all_items_by_pagination")

    @pytest.fixture
    def mock_generation(self, model: Endpoints, mocker: MockerFixture) -> Mock:
        return mocker.spy(model, "_get_all_items_by_generation")

    @pytest.fixture
    def mock_get_page(self, model: Endpoints, mocker: MockerFixture) -> Mock:
        return mocker.spy(model, "_get_page")

    def test_from_handler(self, handler: RequestHandler):
        assert Endpoints.model_validate(handler)._handler is handler
        assert Endpoints.model_validate(dict(handler=handler))._handler is handler

    async def test_get_all_items_skips(
            self, model: Endpoints, url_cursors: list[UrlCursor], mock_pagination: Mock, mock_generation: Mock,
    ):
        cursor = url_cursors[-1]
        assert cursor.next is None

        assert await model._get_all_items(cursor, path="items") == ((), cursor)
        mock_pagination.assert_not_called()
        mock_generation.assert_not_called()

    async def test_get_all_items_by_pagination(
            self,
            model: Endpoints,
            url_cursors: list[UrlCursor],
            items_key: str,
            expected_items: list[dict[str, Any]],
            expected_urls: list[URL],
            mock_url_pages: Mock,
            mock_pagination: Mock,
            mock_generation: Mock,
            mock_get_page: Mock,
            mock_create_model: Mock,
            faker: Faker,
    ):
        items, cursor = await model._get_all_items(url_cursors[0], path=items_key)

        assert len(items) == len(expected_items)
        assert cursor == url_cursors[-1]

        mock_pagination.assert_called_once_with(url_cursors[0], path=items_key, kind=None, show_bar=True)
        mock_generation.assert_not_called()

        actual_cursors = [call.args[0] for call in mock_get_page.call_args_list]
        expected_cursors = [cursor.next for cursor in url_cursors if cursor.next]
        assert actual_cursors == expected_cursors

        # -1 because the last page is not requested as it has no next page
        assert mock_url_pages.call_count == len(url_cursors) - 1
        assert mock_create_model.call_count == len(expected_items)

        urls = [call.args[0] for call in mock_url_pages.call_args_list]
        assert urls == expected_urls

    async def test_get_all_items_by_generation(
            self,
            model: Endpoints,
            index_cursors: list[IndexCursor],
            items_key: str,
            expected_items: list[dict[str, Any]],
            expected_urls: list[URL],
            mock_index_pages: Mock,
            mock_pagination: Mock,
            mock_generation: Mock,
            mock_get_page: Mock,
            mock_create_model: Mock,
            faker: Faker,
    ):
        items, cursor = await model._get_all_items(index_cursors[0], path=items_key)

        assert len(items) == len(expected_items)
        assert cursor == index_cursors[-1]

        mock_pagination.assert_not_called()
        mock_generation.assert_called_once_with(index_cursors[0], path=items_key, kind=None, show_bar=True)

        # async so order is not guaranteed
        actual_cursors = [call.args[0] for call in mock_get_page.call_args_list]
        expected_cursors = [cursor.next for cursor in index_cursors if cursor.next]
        assert sorted(actual_cursors) == sorted(expected_cursors)

        # -1 because the last page is not requested as it has no next page
        assert mock_index_pages.call_count == len(index_cursors) - 1
        assert mock_create_model.call_count == len(expected_items)

        urls = [call.args[0] for call in mock_index_pages.call_args_list]
        assert sorted(urls) == sorted(expected_urls)  # async so order is not guaranteed

    async def test_get_all_items_by_pagination_switches_to_generation(
            self,
            model: Endpoints,
            url_cursors: list[UrlCursor],
            index_cursors: list[IndexCursor],
            items_key: str,
            expected_items: list[dict[str, Any]],
            expected_urls: list[URL],
            mock_index_pages: Mock,
            mock_pagination: Mock,
            mock_generation: Mock,
            mock_get_page: Mock,
            faker: Faker,
    ):
        show_bar = faker.boolean()

        items, cursor = await model._get_all_items_by_pagination(url_cursors[0], path=items_key, show_bar=show_bar)

        assert cursor == index_cursors[-1]
        mock_pagination.assert_called_once_with(url_cursors[0], path=items_key, show_bar=show_bar)
        mock_generation.assert_called_once_with(index_cursors[1], path=items_key, kind=None, show_bar=show_bar)

        # async so order is not guaranteed
        actual_cursors = [call.args[0] for call in mock_get_page.call_args_list]
        expected_cursors = [url_cursors[0].next] + [cursor.next for cursor in index_cursors[1:] if cursor.next]
        assert sorted(actual_cursors) == sorted(expected_cursors)

    @staticmethod
    def assert_get_items_from_response(
            model: Endpoints, response: dict[str, Any], path: str | AliasPath, expected: list[Any]
    ):
        items = list(model._get_items_from_response(response=response, path=path))
        assert items == expected

    def test_get_items_from_response_on_key(self, model: Endpoints, faker: Faker):
        path = "items"
        expected = [faker.word() for _ in range(faker.random_int(1, 10))]
        response = {"items": expected}

        self.assert_get_items_from_response(model, response, path, expected)

    def test_get_items_from_response_on_path(self, model: Endpoints, faker: Faker):
        path = AliasPath("data", "items")
        expected = [{"name": faker.word()} for _ in range(faker.random_int(1, 10))]
        response = {"data": {"items": expected}}

        self.assert_get_items_from_response(model, response, path, expected)

    def test_get_items_from_response_on_nested_path(self, model: Endpoints, faker: Faker):
        path = AliasPath("data", "*", "items", "item")
        expected = [{"name": faker.word()} for _ in range(faker.random_int(1, 10))]
        response = {"data": [{"items": {"item": exp}} for exp in expected]}

        self.assert_get_items_from_response(model, response, path, expected)

    def test_get_items_from_response_on_deeply_nested_path(self, model: Endpoints, faker: Faker):
        path = AliasPath("data", "*", "items", "*", "item", "*", "sub_item")
        expected = [{"name": faker.word()} for _ in range(faker.random_int(1, 10))]
        response = {"data": [{"items": [{"item": [{"sub_item": exp}]}]} for exp in expected]}

        self.assert_get_items_from_response(model, response, path, expected)

    def test_batch_values(self, uris: list[URI]):
        batches = list(Endpoints._batch_values(uris, limit=10))
        for batch in batches[:-1]:
            assert len(batch) == 10
        assert len(batches[-1]) == len(uris) % 10 if len(uris) % 10 != 0 else 10


class TestReadItemEndpoints(EndpointsTester):
    @pytest.fixture
    def model(self, handler: RequestHandler) -> ReadItemEndpoints:
        return ReadItemEndpoints[SimpleURI, MockRemoteResource](
            handler=handler,
        )

    @pytest.mark.parametrize("converter", URI_TYPE_CONVERTERS.values(), ids=URI_TYPE_CONVERTERS.keys())
    async def test_get(
            self,
            model: ReadItemEndpoints,
            uri: URI,
            mock_get: Mock,
            converter: Callable[[URI], Any],
    ):
        await model.get(converter(uri))


class TestReadItemsEndpoints(EndpointsTester):
    class MockReadItemsEndpoints(ReadItemsEndpoints[SimpleURI, MockRemoteResource]):
        _many_url = URL(f"https://api.example.com/{MockRemoteResource.type}s")
        _many_path = "items"
        _many_limit = 26

    @pytest.fixture
    def model(self, handler: RequestHandler) -> ReadItemsEndpoints:
        return self.MockReadItemsEndpoints(handler=handler)

    @pytest.mark.parametrize("converter", URI_TYPE_CONVERTERS.values(), ids=URI_TYPE_CONVERTERS.keys())
    async def test_get_many(
            self,
            model: ReadItemsEndpoints,
            uris: list[URI],
            limit: int,
            items: list[dict[str, Any]],
            mock_get_batched: Mock,
            mock_batch_values: Mock,
            converter: Callable[[URI], Any],
    ):
        await model.get_many(list(map(converter, uris)), limit=limit)
        mock_batch_values.assert_called_once_with(uris, limit)

    async def test_get_many_uses_default_limit(
            self, model: ReadItemsEndpoints, uris: list[URI], mock_batch_values_empty: Mock,
    ):
        await model.get_many(uris)
        mock_batch_values_empty.assert_called_once_with(uris, model._many_limit)

    def test_generate_batch_url(self, uris: list[URI]):
        url = URL("https://api.example.com/resources")
        uris = list(map(str, uris[:10]))

        url = ReadItemsEndpoints._generate_batch_url(url, uris)
        assert url.query["ids"] == ",".join(uris)


class TestReadCollectionEndpoints(EndpointsTester):
    class MockReadCollectionEndpoints(ReadCollectionEndpoints[SimpleURI, MockRemoteCollection]):
        _batch_limit = 26
        _extend_path = "items"
        _extend_type = "type"

    @pytest.fixture
    def model(self, handler: RequestHandler) -> ReadCollectionEndpoints:
        return self.MockReadCollectionEndpoints(handler=handler)

    @pytest.fixture
    def cursor(self, uri: URI, total: int, faker: Faker) -> PageCursor:
        # at least 3 pages to properly test pagination and generation
        limit = faker.random_int(1, 20)
        offset = max(0, total - faker.random_int(limit * 3, total))

        return MockIndexCursor(url=uri.api_url, limit=limit, offset=offset, total=total)

    @pytest.fixture
    def collection(self, uri: URI, cursor: PageCursor, total: int, faker: Faker) -> RemoteCollection:
        return MockRemoteCollection(uri=uri, cursor=cursor, total=total)

    async def test_get_all_from_cursor(
            self, model: ReadCollectionEndpoints, uri: URI, cursor: PageCursor, mock_get_all_items: Mock, faker: Faker
    ):
        expected_items, _ = mock_get_all_items.return_value
        show_bar = faker.boolean()

        result = await model.get_all(cursor, show_bar=show_bar)
        assert result == expected_items

        mock_get_all_items.assert_called_once_with(
            cursor, path=model._extend_path, kind=model._extend_type, show_bar=show_bar
        )

    async def test_get_all_from_collection(
            self,
            model: ReadCollectionEndpoints,
            uri: URI,
            cursor: PageCursor,
            collection: RemoteCollection,
            items: list[dict[str, Any]],
            mock_get_all_items: Mock,
            faker: faker
    ):
        collection.cursor = cursor

        expected_collection = items[:len(items) // 5]
        expected_cursor = deepcopy(cursor)
        mock_get_all_items.return_value = (items[len(items) // 5:], expected_cursor)

        cursor.offset = cursor.total + 1  # set cursor to position after total to simulate missing items
        assert cursor.next is None

        show_bar = faker.boolean()

        with patch.object(collection.__class__, "_items", return_value=expected_collection, new_callable=PropertyMock):
            assert not collection.has_all_items

            result = await model.get_all(collection, show_bar=show_bar)

            assert result == items

            # sets provided cursor to current position - limit when missing items
            assert cursor.offset == max(0, collection.count - cursor.limit)
            assert collection.cursor is not cursor
            assert collection.cursor is expected_cursor

            mock_get_all_items.assert_called_once_with(
                cursor, path=model._extend_path, kind=model._extend_type, show_bar=show_bar
            )


class TestWriteCollectionEndpoints(EndpointsTester):
    class MockWriteCollectionEndpoints(WriteCollectionEndpoints[SimpleURI, MockRemoteResource]):
        _batch_limit = 18
        _extend_path = "items"
        _extend_type = "items"
        _remove_path = "items"

    @pytest.fixture
    def model(self, handler: RequestHandler) -> WriteCollectionEndpoints:
        return self.MockWriteCollectionEndpoints(handler=handler)

    @pytest.fixture
    def collection(self, uri: URI, total: int, faker: Faker) -> RemoteCollection:
        return MockRemoteCollection(uri=uri, cursor=MockUrlCursor(url=faker.url()), total=total)

    @pytest.mark.parametrize("converter", URI_TYPE_CONVERTERS.values(), ids=URI_TYPE_CONVERTERS.keys())
    async def test_add(
            self,
            model: WriteCollectionEndpoints,
            uri: URI,
            uris: list[URI],
            limit: int,
            mock_batch_values: Mock,
            mock_post_batched: Mock,
            faker: Faker,
            converter: Callable[[URI], Any],
    ):
        url = converter(uri)
        to_add = list(map(self._convert_uri_to_random_input_type, uris))

        result = await model.add(url, to_add, limit=limit)

        assert result == len(uris)
        mock_batch_values.assert_called_once_with(uris, limit)

    async def test_add_uses_default_limit(
            self, model: WriteCollectionEndpoints, uri: URI, uris: list[URI], mock_batch_values_empty: Mock
    ):
        await model.add(uri.api_url, uris)
        mock_batch_values_empty.assert_called_once_with(uris, model._batch_limit)

    @pytest.mark.parametrize("converter", URI_TYPE_CONVERTERS.values(), ids=URI_TYPE_CONVERTERS.keys())
    async def test_add_and_skip_duplicates(
            self,
            model: WriteCollectionEndpoints,
            uri: URI,
            uris: list[URI],
            collection: RemoteCollection,
            mock_get: Mock,
            faker: Faker,
            converter: Callable[[URI], Any],
    ):
        uris_duplicated = uris + uris[:faker.random_int(1, len(uris))]
        uris_collection = [
            uris.pop(faker.random_int(0, len(uris) - 1)) for _ in range(faker.random_int(1, len(uris) - 10))
        ]

        assert sorted(uris_collection) != sorted(uris)
        assert sorted(uris_duplicated) != sorted(uris)

        url = converter(uri)
        limit = faker.random_int(1)
        uris_duplicated = list(map(self._convert_uri_to_random_input_type, uris_duplicated))
        collection_items = [MockRemoteResource(uri=uri) for uri in uris_collection]

        # we just want to test that duplicates are skipped when adding, so we mock all surrounding logic
        with (
            patch.object(ReadCollectionEndpoints, "get_all", return_value=collection_items, new_callable=AsyncMock),
            patch.object(WriteCollectionEndpoints, "add", new_callable=AsyncMock) as mock_add
        ):
            await model.add_and_skip_duplicates(url, uris_duplicated, limit=limit)
            mock_add.assert_called_once_with(uri.api_url, uris, limit=limit)

    @pytest.mark.parametrize("converter", URI_TYPE_CONVERTERS.values(), ids=URI_TYPE_CONVERTERS.keys())
    async def test_remove(
            self,
            model: WriteCollectionEndpoints,
            uri: URI,
            uris: list[URI],
            limit: int,
            mock_batch_values: Mock,
            mock_delete_batched: Mock,
            faker: Faker,
            converter: Callable[[URI], Any],
    ):
        url = converter(uri)
        to_remove = list(map(self._convert_uri_to_random_input_type, uris))

        result = await model.remove(url, to_remove, limit=limit)
        assert result == len(uris)

    async def test_remove_uses_default_limit(
            self, model: WriteCollectionEndpoints, uri: URI, uris: list[URI], mock_batch_values_empty: Mock
    ):
        await model.remove(uri.api_url, uris)
        mock_batch_values_empty.assert_called_once_with(uris, model._batch_limit)


class TestReadSavedEndpoints(EndpointsTester):
    class MockReadSavedEndpoints(ReadSavedEndpoints[SimpleURI, MockRemoteResource]):
        _saved_read_url = URL("https://api.example.com/me")
        _saved_path = "items"
        _saved_limit = 15

        source = MockRemoteResource.source
        type = MockRemoteResource.type

    @pytest.fixture
    def model(self, handler: RequestHandler) -> ReadSavedEndpoints:
        return self.MockReadSavedEndpoints(handler=handler)

    @pytest.fixture
    def mock_validate_cursor(self, model: ReadSavedEndpoints, uri: URI, faker: faker) -> Generator[Mock, None, None]:
        cursor = MockInitialCursor(url=uri.api_url)

        with patch.object(TypeAdapter, "validate_python", return_value=cursor) as mock_validate:
            yield mock_validate

    async def test_get_all(
            self, handler: RequestHandler, mock_get_all_items: Mock, mock_validate_cursor: Mock, faker: Faker
    ):
        model = self.MockReadSavedEndpoints(handler=handler)
        limit = faker.random_int(1, 100)
        show_bar = faker.boolean()

        await model.get_all(limit=limit, show_bar=show_bar)

        mock_validate_cursor.assert_called_once_with(dict(
            url=self.MockReadSavedEndpoints._saved_read_url, limit=limit
        ))
        mock_get_all_items.assert_called_once_with(
            mock_validate_cursor.return_value,
            path=self.MockReadSavedEndpoints._saved_path,
            kind=self.MockReadSavedEndpoints.type,
            show_bar=show_bar,
        )

    async def test_get_all_uses_default_limit(self, model: ReadSavedEndpoints, mock_validate_cursor: Mock):
        await model.get_all()
        mock_validate_cursor.assert_called_once_with(dict(
            url=self.MockReadSavedEndpoints._saved_read_url, limit=model._saved_limit
        ))


class TestWriteSavedEndpoints(EndpointsTester):
    class MockWriteSavedEndpoints(WriteSavedEndpoints[SimpleURI, MockRemoteResource]):
        _saved_write_url = URL("https://api.example.com/me")
        _saved_path = "items"
        _saved_limit = 12

        _batch_limit = 72

    @pytest.fixture
    def model(self, handler: RequestHandler) -> WriteSavedEndpoints:
        return self.MockWriteSavedEndpoints(handler=handler)

    async def test_add_many(
            self,
            model: WriteSavedEndpoints,
            uris: list[URI],
            limit: int,
            mock_batch_values: Mock,
            mock_put_batched: Mock,
            faker: Faker,
    ):
        to_add = list(map(self._convert_uri_to_random_input_type, uris))

        result = await model.add_many(to_add, limit=limit)
        assert result == len(uris)

    async def test_add_many_uses_default_limit(
            self, model: WriteSavedEndpoints, uris: list[URI], mock_batch_values_empty: Mock
    ):
        await model.add_many(uris)
        mock_batch_values_empty.assert_called_once_with(uris, model._batch_limit)

    async def test_remove_many(
            self,
            model: WriteSavedEndpoints,
            uris: list[URI],
            limit: int,
            mock_batch_values: Mock,
            mock_delete_batched: Mock,
            faker: Faker,
    ):
        to_remove = list(map(self._convert_uri_to_random_input_type, uris))

        result = await model.remove_many(to_remove, limit=limit)
        assert result == len(uris)

    async def test_remove_many_uses_default_limit(
            self, model: WriteSavedEndpoints, uris: list[URI], mock_batch_values_empty: Mock
    ):
        await model.remove_many(uris)
        mock_batch_values_empty.assert_called_once_with(uris, model._batch_limit)
