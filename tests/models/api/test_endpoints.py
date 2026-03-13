import math
from collections.abc import Callable, Generator, Sequence
from copy import deepcopy
from typing import Any, final
from unittest.mock import patch, Mock, AsyncMock, PropertyMock

import pytest
from aiorequestful.request import RequestHandler
from faker import Faker
from pydantic import AliasPath, TypeAdapter
from yarl import URL

from musify.exception import MusifyTypeError
from musify.models.api import Endpoints, ReadItemEndpoints, ReadItemsEndpoints, \
    ReadSavedEndpoints, WriteCollectionEndpoints, WriteSavedEndpoints, ReadCollectionEndpoints
from musify.models.collection import RemoteCollection
from musify.models.cursors import PageCursor, IndexCursor
from musify.models.item.album import RemoteAlbum
from musify.models.item.artist import RemoteArtist
from musify.models.item.track import RemoteTrack
from musify.models.properties.uri import URI
from tests.models.api.testers import EndpointsTester, URI_TYPE_CONVERTERS
from tests.models.api.utils import MockRemoteResource, MockRemoteCollection, MockIndexCursor, MockUrlCursor
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
        with pytest.raises(MusifyTypeError, match="Can only create resources from final API models"):
            Endpoints.create_model({})

    def test_create_fails_on_unmatched_source(self):
        @final
        class MockEndpointsTest(Endpoints[SimpleURI, MockRemoteResource]):
            __final__ = True
            source = "unknown_source"
            type = MockRemoteResource.type

        with pytest.raises(MusifyTypeError, match="No registered resource models found"):
            MockEndpointsTest.create_model({})

    def test_create_fails_on_unmatched_kind(self):
        @final
        class MockEndpointsTest(Endpoints[SimpleURI, MockRemoteResource]):
            __final__ = True
            source = MockRemoteResource.source
            type = "unknown_type"

        with pytest.raises(MusifyTypeError, match=f"Could not find a registered {MockRemoteResource.source!r} model"):
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
    def initial_cursor(self, uri: URI, faker: Faker) -> PageCursor:
        limit = faker.random_int(1, 20)
        offset = faker.random_int(1, 100)
        total = offset + limit * faker.random_int(3, 10)
        return MockIndexCursor(url=uri.api_url, limit=limit, offset=offset, total=total)

    @pytest.fixture
    def offset_cursors(self, initial_cursor: IndexCursor, uri: URI, faker: Faker) -> list[IndexCursor]:
        cursors = list(initial_cursor.iter_pages)
        assert len(set(cursor.offset for cursor in cursors)) == len(cursors)
        assert len(set(cursor.url for cursor in cursors)) == len(cursors)
        assert cursors[-1].offset + cursors[-1].limit > initial_cursor.total
        assert cursors[-2].offset + cursors[-2].limit <= initial_cursor.total
        assert cursors[-1].next is None

        return cursors

    def test_from_handler(self, handler: RequestHandler):
        assert Endpoints.model_validate(handler)._handler is handler
        assert Endpoints.model_validate(dict(handler=handler))._handler is handler

    async def test_get_all_items_picks_pagination(self, model: Endpoints, initial_cursor: IndexCursor):
        cursor = MockUrlCursor(url=initial_cursor.url, next=initial_cursor.next.url)

        with (
            patch.object(model.__class__, "_get_all_items_by_pagination") as mock_pagination,
            patch.object(model.__class__, "_get_all_items_by_generation") as mock_generation,
        ):
            await model._get_all_items(cursor, path="items")
            mock_pagination.assert_called_once()
            mock_generation.assert_not_called()

    async def test_get_all_items_picks_generation(self, model: Endpoints, initial_cursor: IndexCursor, faker: Faker):
        initial_cursor.offset = faker.random_int(1, 100)
        initial_cursor.limit = faker.random_int(1, 100)
        initial_cursor.total = faker.random_int(1, 100)

        with (
            patch.object(model.__class__, "_get_all_items_by_pagination") as mock_pagination,
            patch.object(model.__class__, "_get_all_items_by_generation") as mock_generation,
        ):
            await model._get_all_items(initial_cursor, path="items")
            mock_pagination.assert_not_called()
            mock_generation.assert_called_once()

    async def test_get_all_items_by_pagination(
            self,
            model: Endpoints,
            uri: URI,
            initial_cursor: IndexCursor,
            offset_cursors: list[IndexCursor],
            faker: Faker,
    ):
        url_cursors = [MockUrlCursor(url=initial_cursor.url, next=initial_cursor.next.url)]
        for cursor in offset_cursors:
            cursor = MockUrlCursor(url=cursor.url, next=cursor.next.url if cursor.next else None)
            url_cursors.append(cursor)

        total = initial_cursor.total
        available_items = [{"name": faker.word()} for _ in range(total)]
        expected_items = available_items[:total - offset_cursors[0].offset]
        available_items = expected_items.copy()
        expected_urls = [cursor.url for cursor in offset_cursors]
        iter_cursors = iter(url_cursors[1:])  # skip initial cursor which is used for the first request

        def _get_items_from_response(*_, **__) -> Sequence[dict]:
            return [available_items.pop() for _ in range(initial_cursor.limit) if available_items]

        def _return_cursor(*_, **__) -> PageCursor:
            return next(iter_cursors)

        def _return_response[T](item: T, *_, **__) -> T:
            return item

        with (
            patch.object(RequestHandler, "get", side_effect=_return_cursor, new_callable=AsyncMock) as mock_get,
            patch.object(
                model.__class__, "_get_items_from_response", side_effect=_get_items_from_response
            ) as mock_get_items_from_response,
            patch.object(model.__class__, "create_model", side_effect=_return_response) as mock_create_model,
        ):
            items, cursor = await model._get_all_items_by_pagination(url_cursors[0], path="items")
            assert len(items) == len(expected_items)
            assert cursor == url_cursors[-1]

            assert mock_get_items_from_response.call_count == len(offset_cursors)
            assert mock_create_model.call_count == len(expected_items)

            urls = [call.args[0] for call in mock_get.call_args_list]
            assert urls == expected_urls

    async def test_get_all_items_by_generation(
            self,
            model: Endpoints,
            uri: URI,
            initial_cursor: IndexCursor,
            offset_cursors: list[IndexCursor],
            faker: Faker,
    ):
        total = initial_cursor.total
        available_items = [{"name": faker.word()} for _ in range(total)]
        expected_items = available_items[:total - offset_cursors[0].offset]
        expected_urls = [cursor.url for cursor in offset_cursors]

        def _get_response(url: URL, *_, **__) -> dict:
            limit = int(url.query["limit"])
            offset = int(url.query["offset"])
            next_offset = offset + limit

            response_items = available_items[offset:next_offset]
            response_cursor = next(c for c in offset_cursors if c.offset == offset)
            return {"cursor": response_cursor, "items": response_items}

        def _get_cursor_from_response(response: dict[str, Any], *_, **__) -> PageCursor:
            return response["cursor"]

        def _get_items_from_response(response: dict[str, Any], *_, **__) -> list[dict]:
            return response["items"]

        def _return_item[T](item: T, *_, **__) -> T:
            return item

        with (
            patch.object(
                initial_cursor.__class__, "iter_pages", return_value=offset_cursors, new_callable=PropertyMock
            ),
            patch.object(RequestHandler, "get", side_effect=_get_response, new_callable=AsyncMock) as mock_get,
            patch.object(
                model.__class__, "_get_items_from_response", side_effect=_get_items_from_response
            ) as mock_get_items_from_response,
            patch.object(model.__class__, "create_model", side_effect=_return_item) as mock_create_model,
            patch.object(PageCursor, "get_cursor_from_response", side_effect=_get_cursor_from_response),
        ):
            items, cursor = await model._get_all_items_by_generation(initial_cursor, path="items")
            assert len(items) == len(expected_items)
            assert cursor == offset_cursors[-1]

            assert mock_get_items_from_response.call_count == len(offset_cursors)
            assert mock_create_model.call_count == len(expected_items)

            urls = [call.args[0] for call in mock_get.call_args_list]
            assert sorted(urls) == sorted(expected_urls)  # async so order is not guaranteed

    async def test_get_all_items_by_pagination_switches_to_generation(
            self,
            model: Endpoints,
            uri: URI,
            initial_cursor: IndexCursor,
            offset_cursors: list[IndexCursor],
            faker: Faker,
    ):
        total = initial_cursor.total
        expected_items = [{"name": faker.word()} for _ in range(total)]

        pagination_items = expected_items[:total // 2]
        generation_items = expected_items[total // 2:]

        with (
            patch.object(RequestHandler, "get", return_value=pagination_items, new_callable=AsyncMock) as mock_get,
            patch.object(
                model.__class__, "_get_items_from_response", return_value=pagination_items
            ) as mock_get_items_from_response,
            patch.object(model.__class__, "create_model", return_value=pagination_items) as mock_create_model,
            patch.object(PageCursor, "get_cursor_from_response", return_value=offset_cursors[0]) as mock_get_cursor,
            patch.object(
                model.__class__,
                "_get_all_items_by_generation",
                return_value=(generation_items, offset_cursors[-1]),
                new_callable=AsyncMock
            ) as mock_generation,
        ):
            items, cursor = await model._get_all_items_by_pagination(initial_cursor, path="items")
            assert len(items) == len(expected_items)
            assert cursor == offset_cursors[-1]

            assert mock_get.call_count == 1
            assert mock_get_items_from_response.call_count == 1
            assert mock_create_model.call_count == len(expected_items[:total // 2])
            assert mock_get_cursor.call_count == 1
            assert mock_generation.call_count == 1
            mock_generation.assert_called_once_with(cursor=mock_get_cursor.return_value, path="items", kind=None)

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

    def test_batch_items(self, uris: list[URI]):
        batches = list(Endpoints._batch_items(uris, limit=10))
        for batch in batches[:-1]:
            assert len(batch) == 10
        assert len(batches[-1]) == len(uris) % 10 if len(uris) % 10 != 0 else 10

    def test_generate_batch_url(self, uris: list[URI]):
        url = URL("https://api.example.com/resources")
        uris = list(map(str, uris[:10]))

        url = Endpoints._generate_batch_url(url, uris)
        assert url.query["ids"] == ",".join(uris)


class TestReadItemEndpoints(EndpointsTester):
    @pytest.fixture
    def model(self, handler: RequestHandler) -> Endpoints:
        return ReadItemEndpoints[SimpleURI, MockRemoteResource](
            handler=handler,
        )

    @pytest.fixture
    def response(self, uri: URI) -> dict[str, Any]:
        return {"id": uri.id, "uri": str(uri)}

    @pytest.fixture
    def mock_get(self, uri: URI, response: dict[str, Any]) -> Generator[Mock, None, None]:
        with patch.object(RequestHandler, "get", return_value=response) as mock_get:
            yield mock_get
            mock_get.assert_called_once_with(uri.api_url)

    @pytest.fixture
    def mock_create_model(self, model: Endpoints, response: dict[str, Any]) -> Generator[Mock, None, None]:
        with patch.object(model.__class__, "create_model") as mock_create_model:
            yield mock_create_model
            mock_create_model.assert_called_once_with(response)

    @pytest.mark.parametrize("converter", URI_TYPE_CONVERTERS.values(), ids=URI_TYPE_CONVERTERS.keys())
    async def test_get_on_uri(
            self,
            model: Endpoints,
            uri: URI,
            mock_get: Mock,
            mock_create_model: Mock,
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

    @pytest.fixture
    def mock_get_items_from_response(
            self, model: ReadItemsEndpoints, uris: list[URI], limit: int
    ) -> Generator[Mock, None, None]:
        expected = math.ceil(len(uris) / limit)

        with patch.object(
                model.__class__, "_get_items_from_response"
        ) as mock_get_items_from_response:
            yield mock_get_items_from_response
            assert mock_get_items_from_response.call_count == expected

    @pytest.mark.parametrize("converter", URI_TYPE_CONVERTERS.values(), ids=URI_TYPE_CONVERTERS.keys())
    async def test_get_many(
            self,
            model: ReadItemsEndpoints,
            uris: list[URI],
            limit: int,
            mock_get: Mock,
            mock_batch_items: Mock,
            mock_get_items_from_response: Mock,
            converter: Callable[[URI], Any],
    ):
        await model.get_many(list(map(converter, uris)), limit=limit)

    async def test_get_many_uses_default_limit(self, model: ReadItemsEndpoints, uris: list[URI]):
        with patch.object(model.__class__, "_batch_items", return_value=[]) as mock_batch_items:
            await model.get_many(uris)
            mock_batch_items.assert_called_once_with(uris, model._many_limit)


class TestReadCollectionEndpoints(EndpointsTester):
    class MockReadCollectionEndpoints(ReadCollectionEndpoints[SimpleURI, MockRemoteCollection]):
        _batch_limit = 26
        _extend_path = "items"
        _extend_type = "type"

    @pytest.fixture
    def model(self, handler: RequestHandler) -> ReadCollectionEndpoints:
        return self.MockReadCollectionEndpoints(handler=handler)

    @pytest.fixture
    def cursor(self, uri: URI, faker: Faker) -> PageCursor:
        limit = faker.random_int(1, 20)
        offset = faker.random_int(1, 100)
        total = offset + limit * faker.random_int(3, 10)
        return MockIndexCursor(url=uri.api_url, limit=limit, offset=offset, total=total)

    @pytest.fixture
    @patch.multiple(
        RemoteCollection,
        __abstractmethods__=set(),
        _items=PropertyMock(),
    )
    def collection(self, uri: URI, cursor: PageCursor, faker: Faker) -> RemoteCollection:
        return RemoteCollection(
            uri=uri,
            cursor=cursor,
            total=faker.random_int(),
        )

    async def test_get_all_from_cursor(self, model: ReadCollectionEndpoints, uri: URI, cursor: PageCursor):
        expected = [1, 2, 3]

        with patch.object(
                model.__class__, "_get_all_items", return_value=(expected, cursor), new_callable=AsyncMock
        ) as mock_get_all_items:
            result = await model.get_all(cursor)
            assert result == expected

            mock_get_all_items.assert_called_once_with(cursor=cursor, path=model._extend_path, kind=model._extend_type)

    async def test_get_all_from_collection(
            self, model: ReadCollectionEndpoints, uri: URI, cursor: PageCursor, collection: RemoteCollection
    ):
        collection.cursor = cursor
        expected_collection = [1, 2, 3]
        expected_get = [4, 5, 6]
        expected_cursor = deepcopy(cursor)

        cursor.offset = cursor.total + 1  # set cursor to position after total to simulate missing items
        assert cursor.next is None

        with (
            patch.object(collection.__class__, "_items", return_value=expected_collection, new_callable=PropertyMock),
            patch.object(
                model.__class__,
                "_get_all_items",
                return_value=(expected_get, expected_cursor),
                new_callable=AsyncMock
            ) as mock_get_all_items
        ):
            assert not collection.has_all_items
            result = await model.get_all(collection)
            assert result == expected_collection + expected_get

            mock_get_all_items.assert_called_once_with(cursor=cursor, path=model._extend_path, kind=model._extend_type)
            # sets current cursor to current position - limit when missing items
            assert cursor.offset == max(0, collection.count - cursor.limit)
            assert collection.cursor is not cursor
            assert collection.cursor is expected_cursor


class TestWriteCollectionEndpoints(EndpointsTester):
    class MockWriteCollectionEndpoints(WriteCollectionEndpoints[SimpleURI, MockRemoteResource]):
        _batch_limit = 18
        _extend_path = "items"
        _remove_path = "items"

    @pytest.fixture
    def model(self, handler: RequestHandler) -> WriteCollectionEndpoints:
        return self.MockWriteCollectionEndpoints(handler=handler)

    @pytest.fixture
    @patch.multiple(
        RemoteCollection,
        __abstractmethods__=set(),
        _items=PropertyMock(),
    )
    def collection(self, uri: URI, faker: Faker) -> RemoteCollection:
        return RemoteCollection(uri=uri, cursor=MockUrlCursor(url=uri.api_url), total=faker.random_int())

    # noinspection PyMethodOverriding
    @pytest.fixture
    def mock_get(
            self, model: WriteCollectionEndpoints, uri: URI, collection: RemoteCollection
    ) -> Generator[Mock, None, None]:
        with patch.object(model.__class__, "get", return_value=collection, new_callable=AsyncMock) as mock_get:
            yield mock_get
            mock_get.assert_called_once_with(uri.api_url)

    @pytest.mark.parametrize("converter", URI_TYPE_CONVERTERS.values(), ids=URI_TYPE_CONVERTERS.keys())
    async def test_append(
            self,
            model: WriteCollectionEndpoints,
            uri: URI,
            uris: list[URI],
            limit: int,
            mock_batch_items: Mock,
            mock_post: Mock,
            faker: Faker,
            converter: Callable[[URI], Any],
    ):
        url = converter(uri)
        uris = list(map(self._convert_uri_to_random_input_type, uris))
        result = await model.append(url, uris, limit=limit)
        assert result == len(uris)

    async def test_append_uses_default_limit(self, model: WriteCollectionEndpoints, uri: URI, uris: list[URI]):
        with patch.object(model.__class__, "_batch_items", return_value=[]) as mock_batch_items:
            await model.append(uri.api_url, uris)
            mock_batch_items.assert_called_once_with(uris, model._batch_limit)

    @pytest.mark.parametrize("converter", URI_TYPE_CONVERTERS.values(), ids=URI_TYPE_CONVERTERS.keys())
    async def test_append_and_skip_duplicates(
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

        assert sorted(map(str, uris_collection)) != sorted(map(str, uris))
        assert sorted(map(str, uris_duplicated)) != sorted(map(str, uris))

        url = converter(uri)
        limit = faker.random_int(1)
        uris_duplicated = list(map(self._convert_uri_to_random_input_type, uris_duplicated))
        collection_items = [MockRemoteResource(uri=uri) for uri in uris_collection]

        with (
            patch.object(model.__class__, "get_all", return_value=collection_items, new_callable=AsyncMock),
            patch.object(model.__class__, "append", new_callable=AsyncMock) as mock_append
        ):
            await model.append_and_skip_duplicates(url, uris_duplicated, limit=limit)
            mock_append.assert_called_once_with(uri.api_url, uris, limit=limit)

    @pytest.mark.parametrize("converter", URI_TYPE_CONVERTERS.values(), ids=URI_TYPE_CONVERTERS.keys())
    async def test_remove(
            self,
            model: WriteCollectionEndpoints,
            uri: URI,
            uris: list[URI],
            limit: int,
            mock_batch_items: Mock,
            mock_delete: Mock,
            faker: Faker,
            converter: Callable[[URI], Any],
    ):
        url = converter(uri)
        uris = list(map(self._convert_uri_to_random_input_type, uris))
        result = await model.remove(url, uris, limit=limit)
        assert result == len(uris)

    async def test_remove_uses_default_limit(self, model: WriteCollectionEndpoints, uri: URI, uris: list[URI]):
        with patch.object(model.__class__, "_batch_items", return_value=[]) as mock_batch_items:
            await model.remove(uri.api_url, uris)
            mock_batch_items.assert_called_once_with(uris, model._batch_limit)


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

    async def test_get_all(self, handler: RequestHandler, uri: URI, faker: Faker):
        model = self.MockReadSavedEndpoints(handler=handler)
        limit = faker.random_int(1, 100)

        with (
            patch.object(
                TypeAdapter, "validate_python", return_value=MockUrlCursor(url=uri.api_url)
            ) as mock_validate,
            patch.object(
                model.__class__, "_get_all_items_by_pagination", return_value=([1], None)
            ) as mock_get_all_items,
        ):
            await model.get_all(limit=limit)

            mock_validate.assert_called_once_with(dict(
                url=self.MockReadSavedEndpoints._saved_read_url, limit=limit
            ))
            mock_get_all_items.assert_called_once_with(
                cursor=mock_validate.return_value,
                path=self.MockReadSavedEndpoints._saved_path,
                kind=self.MockReadSavedEndpoints.type,
            )

    async def test_get_all_uses_default_limit(self, model: ReadSavedEndpoints, uri: URI):
        with (
            patch.object(
                TypeAdapter, "validate_python", return_value=MockUrlCursor(url=uri.api_url)
            ) as mock_validate,
            patch.object(model.__class__, "_get_all_items_by_pagination", return_value=([1], None)),
        ):
            await model.get_all()
            mock_validate.assert_called_once_with(dict(
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
            mock_batch_items: Mock,
            mock_put: Mock,
            faker: Faker,
    ):
        uris = list(map(self._convert_uri_to_random_input_type, uris))
        await model.add_many(uris, limit=limit)

    async def test_add_many_uses_default_limit(self, model: WriteSavedEndpoints, uris: list[URI]):
        with patch.object(model.__class__, "_batch_items", return_value=[]) as mock_batch_items:
            await model.add_many(uris)
            mock_batch_items.assert_called_once_with(uris, model._batch_limit)

    async def test_remove_many(
            self,
            model: WriteSavedEndpoints,
            uris: list[URI],
            limit: int,
            mock_batch_items: Mock,
            mock_delete: Mock,
            faker: Faker,
    ):
        uris = list(map(self._convert_uri_to_random_input_type, uris))
        await model.remove_many(uris, limit=limit)

    async def test_remove_many_uses_default_limit(self, model: WriteSavedEndpoints, uris: list[URI]):
        with patch.object(model.__class__, "_batch_items", return_value=[]) as mock_batch_items:
            await model.remove_many(uris)
            mock_batch_items.assert_called_once_with(uris, model._batch_limit)
