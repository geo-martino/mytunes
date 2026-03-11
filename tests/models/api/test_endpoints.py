import math
from collections.abc import Callable, Generator
from copy import deepcopy
from typing import Any, final
from unittest.mock import patch, Mock, AsyncMock, PropertyMock

import pytest
from aiorequestful.request import RequestHandler
from faker import Faker
from pydantic import AliasPath
from yarl import URL

from musify.exception import MusifyTypeError
from musify.models.properties.uri import URI
from musify.models.api import Endpoints, ReadItemEndpoints, ReadItemsEndpoints, \
    ReadSavedEndpoints, WriteCollectionEndpoints, WriteSavedEndpoints, ReadCollectionEndpoints
from musify.models.collection import ItemsCursor, RemoteCollection
from musify.models.item.album import RemoteAlbum
from musify.models.item.artist import RemoteArtist
from musify.models.item.track import RemoteTrack
from tests.models.api.testers import EndpointsTester, URI_TYPE_CONVERTERS
from tests.models.api.utils import MockRemoteResource, MockRemoteCollection
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
    def cursor_initial(self, uri: URI, faker: Faker) -> ItemsCursor:
        return ItemsCursor(current=uri.api_url, limit=20, offset=0)

    @pytest.fixture
    def cursors(self, cursor_initial: ItemsCursor, uri: URI, faker: Faker) -> list[ItemsCursor]:
        cursor_initial.next = cursor_initial.current.update_query(offset=0)

        cursors = []
        cursor_current = deepcopy(cursor_initial)
        for _ in range(faker.random_int(2, 10)):
            cursor_current.offset += cursor_current.limit
            offset_next = cursor_current.offset + cursor_current.limit
            cursor_current.next = cursor_current.current.update_query(offset=offset_next)

            cursors.append(cursor_current)
            cursor_current = deepcopy(cursor_current)

        cursors[-1].next = None  # set last cursor's next to None to end the pagination

        assert len(set(cursor.offset for cursor in cursors)) == len(cursors)
        assert len(set(cursor.next for cursor in cursors)) == len(cursors)
        assert len(set(cursor.current for cursor in cursors)) == len(cursors)

        return cursors

    @pytest.fixture
    def mock_get_next_cursor(self, cursors: list[dict[str, Any]]) -> Generator[dict[str, Any], None, None]:
        iter_cursors = iter(cursors)
        with patch.object(RequestHandler, "get", side_effect=lambda *_: next(iter_cursors)) as mock_get:
            yield mock_get

    def test_from_handler(self, handler: RequestHandler):
        assert Endpoints.model_validate(handler)._handler is handler
        assert Endpoints.model_validate(dict(handler=handler))._handler is handler

    def test_create_saved_items_cursor(self, uri: URI, faker: Faker):
        limit = faker.random_int(1, 100)
        offset = faker.random_int(1, 100)

        cursor = Endpoints._create_saved_items_cursor(uri.api_url, limit=limit, offset=offset)
        assert cursor.limit == limit
        assert cursor.offset == offset
        assert cursor.current == uri.api_url.with_query(limit=limit, offset=offset)
        assert cursor.next == cursor.current
        assert cursor.previous is None

    async def test_get_all_items_from_cursor(
            self,
            model: Endpoints,
            uri: URI,
            cursor_initial: ItemsCursor,
            cursors: list[ItemsCursor],
            mock_get_next_cursor: Mock,
            faker: Faker,
    ):
        expected = [{"name": faker.word()} for _ in range(faker.random_int(1, 10))]

        def _return_response[T](item: T, *_, **__) -> T:
            return item

        with (
            patch.object(
                model.__class__, "_get_items_from_response", return_value=expected
            ) as mock_get_items_from_response,
            patch.object(model.__class__, "create_model", side_effect=_return_response) as mock_create_model,
        ):
            items, cursor = await model._get_all_items_from_cursor(cursor_initial, path="items")
            assert len(list(items)) == len(expected) * len(cursors)

            assert mock_get_items_from_response.call_count == len(cursors)
            assert mock_create_model.call_count == len(expected) * len(cursors)

            urls = [call.args[0] for call in mock_get_next_cursor.call_args_list]
            assert urls == [cursor_initial.next] + [cursor.next for cursor in cursors if cursor.next is not None]

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
    def cursor(self, uri: URI, faker: Faker) -> ItemsCursor:
        return ItemsCursor(current=uri.api_url, limit=20, offset=0)

    @pytest.fixture
    @patch.multiple(
        RemoteCollection,
        __abstractmethods__=set(),
        _items=PropertyMock(),
    )
    def collection(self, uri: URI, cursor: ItemsCursor, faker: Faker) -> RemoteCollection:
        return RemoteCollection(
            uri=uri,
            cursor=cursor,
            total=faker.random_int(),
        )

    async def test_get_all_from_cursor(self, model: ReadCollectionEndpoints, uri: URI, cursor: ItemsCursor):
        expected = [1, 2, 3]

        with patch.object(
                model.__class__, "_get_all_items_from_cursor", return_value=(expected, cursor), new_callable=AsyncMock
        ) as mock_get_all_items:
            result = await model.get_all(cursor)
            assert result == expected

            mock_get_all_items.assert_called_once_with(cursor=cursor, path=model._extend_path, kind=model._extend_type)

    async def test_get_all_from_collection(
            self, model: ReadCollectionEndpoints, uri: URI, cursor: ItemsCursor, collection: RemoteCollection
    ):
        collection.cursor = cursor
        expected_collection = [1, 2, 3]
        expected_get = [4, 5, 6]
        expected_cursor = deepcopy(cursor)

        assert cursor.next is None

        with (
            patch.object(collection.__class__, "_items", return_value=expected_collection, new_callable=PropertyMock),
            patch.object(
                model.__class__,
                "_get_all_items_from_cursor",
                return_value=(expected_get, expected_cursor),
                new_callable=AsyncMock
            ) as mock_get_all_items
        ):
            result = await model.get_all(collection)
            assert result == expected_collection + expected_get

            mock_get_all_items.assert_called_once_with(cursor=cursor, path=model._extend_path, kind=model._extend_type)
            assert cursor.next == cursor.current  # sets next cursor to current when collection is empty
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
        return RemoteCollection(
            uri=uri,
            cursor=ItemsCursor(current=uri.api_url, limit=20, offset=0),
            total=faker.random_int(),
        )

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
        offset = faker.random_int(1, 100)

        with (
            patch.object(
                model.__class__, "_create_saved_items_cursor", return_value=ItemsCursor(current=uri.api_url)
            ) as mock_create_saved_items_cursor,
            patch.object(model.__class__, "_get_all_items_from_cursor", return_value=([1], None)) as mock_get_all_items,
        ):
            await model.get_all(limit=limit, offset=offset)

            mock_create_saved_items_cursor.assert_called_once_with(
                self.MockReadSavedEndpoints._saved_read_url, limit=limit, offset=offset
            )
            mock_get_all_items.assert_called_once_with(
                cursor=mock_create_saved_items_cursor.return_value,
                path=self.MockReadSavedEndpoints._saved_path,
                kind=self.MockReadSavedEndpoints.type,
            )

    async def test_get_all_uses_default_limit(self, model: ReadSavedEndpoints, uri: URI):
        with (
            patch.object(
                model.__class__, "_create_saved_items_cursor", return_value=ItemsCursor(current=uri.api_url)
            ) as mock_create_model_cursor,
            patch.object(model.__class__, "_get_all_items_from_cursor", return_value=([1], None)),
        ):
            await model.get_all()
            mock_create_model_cursor.assert_called_once_with(
                self.MockReadSavedEndpoints._saved_read_url, limit=model._saved_limit, offset=None
            )


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
