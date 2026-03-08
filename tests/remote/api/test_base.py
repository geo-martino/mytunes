import math
from collections.abc import Callable
from copy import deepcopy
from typing import Any, Generator, final
from unittest.mock import patch, Mock

import pytest
from aiorequestful.auth import Authoriser
from aiorequestful.request import RequestHandler
from faker import Faker
from pydantic import AliasPath
from yarl import URL

from musify.exception import MusifyTypeError
from musify.models.properties.uri import URI
from musify.remote.api import RemoteEndpoints, RemoteGetSingleEndpoints, RemoteGetManyEndpoints, RemoteGetSavedEndpoints
from musify.remote.api._base import RemoteMutableCollectionEndpoints, RemoteMutableSavedEndpoints
from musify.remote.collection import ItemsCursor
from musify.remote.item.album import RemoteAlbum
from musify.remote.item.artist import RemoteArtist
from musify.remote.item.track import RemoteTrack
from tests.remote.api.testers import RemoteEndpointsTester, URI_TYPE_CONVERTERS
from tests.remote.api.utils import MockRemoteResource
from tests.utils import SimpleURI


class TestCreateFromResponse:
    @final
    class MockRemoteEndpoints(RemoteEndpoints[Authoriser, SimpleURI, MockRemoteResource]):
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
            RemoteEndpoints.create({})

    def test_create_fails_on_unmatched_source(self):
        @final
        class MockRemoteEndpointsSub(RemoteEndpoints[Authoriser, SimpleURI, MockRemoteResource]):
            __final__ = True
            source = "unknown_source"
            type = MockRemoteResource.type

        with pytest.raises(MusifyTypeError, match="No registered resource models found"):
            MockRemoteEndpointsSub.create({})

    def test_creates_current_kind(self, faker: Faker):
        uri = SimpleURI.from_id(faker.random_int(1, 100), kind=self.MockRemoteEndpoints.type)

        result = self.MockRemoteEndpoints.create(dict(name=faker.word(), uri=uri))
        assert isinstance(result, MockRemoteResource)
        assert result.type == self.MockRemoteEndpoints.type

    def test_creates_given_kind(self, faker: Faker):
        types = [
            RemoteTrack.type,
            RemoteAlbum.type,
            RemoteArtist.type,
        ]
        types.remove(self.MockRemoteEndpoints.type)
        expected_type = faker.random_element(types)

        uri = SimpleURI.from_id(faker.random_int(1, 100), kind=expected_type)

        result = self.MockRemoteEndpoints.create(dict(name=faker.word(), uri=uri), kind=expected_type)
        assert isinstance(result, MockRemoteResource)
        assert result.type != self.MockRemoteEndpoints.type
        assert result.type == expected_type


class TestRemoteEndpoints(RemoteEndpointsTester):
    @pytest.fixture
    def model(self, handler: RequestHandler) -> RemoteEndpoints:
        return RemoteEndpoints[Authoriser, SimpleURI, MockRemoteResource](
            handler=handler,
        )

    @pytest.fixture
    def cursor_initial(self, uri: URI, faker: Faker) -> ItemsCursor:
        cursor_initial = ItemsCursor(current=uri.api_url, limit=20, offset=0)
        offset_next = cursor_initial.offset + cursor_initial.limit
        cursor_initial.next = cursor_initial.current.update_query(offset=offset_next)
        return cursor_initial

    @pytest.fixture
    def cursors(self, cursor_initial: ItemsCursor, uri: URI, faker: Faker) -> list[ItemsCursor]:
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

    def test_create_saved_items_cursor(self, uri: URI, faker: Faker):
        limit = faker.random_int(1, 100)
        offset = faker.random_int(1, 100)

        cursor = RemoteEndpoints._create_saved_items_cursor(uri.api_url, limit=limit, offset=offset)
        assert cursor.limit == limit
        assert cursor.offset == offset
        assert cursor.current == uri.api_url.with_query(limit=limit, offset=offset)
        assert cursor.next == cursor.current
        assert cursor.previous is None

    async def test_extend_items_from_cursor(
            self,
            model: RemoteEndpoints,
            uri: URI,
            cursor_initial: ItemsCursor,
            cursors: list[ItemsCursor],
            mock_get_next_cursor: Mock,
    ):
        with patch.object(RemoteEndpoints, "_extend_items_from_response") as mock_extend_items_from_response:
            await model._extend_items_from_cursor([], cursor_initial, path="items")

            assert mock_extend_items_from_response.call_count == len(cursors)

            urls = [call.args[0] for call in mock_get_next_cursor.call_args_list]
            assert urls == [cursor_initial.next] + [cursor.next for cursor in cursors if cursor.next is not None]

    def test_extend_items_from_response_on_key(self, model: RemoteEndpoints, faker: Faker):
        expected = [faker.word() for _ in range(faker.random_int(1, 10))]
        response = {"items": expected}

        def _return_response[T](item: T, *_, **__) -> T:
            return item

        items = []
        with patch.object(RemoteEndpoints, "create", side_effect=_return_response) as mock_create:
            model._extend_items_from_response(items, response=response, path="items")
            assert items == expected
            assert mock_create.call_count == len(items)

    def test_extend_items_from_response_on_path(self, model: RemoteEndpoints, faker: Faker):
        expected = [faker.word() for _ in range(faker.random_int(1, 10))]
        response = {"data": {"items": expected}}

        def _return_response[T](item: T, *_, **__) -> T:
            return item

        items = []
        with patch.object(RemoteEndpoints, "create", side_effect=_return_response) as mock_create:
            model._extend_items_from_response(items, response=response, path=AliasPath("data", "items"))
            assert items == expected
            assert mock_create.call_count == len(items)

    def test_batch_items(self, uris: list[URI]):
        batches = list(RemoteEndpoints._batch_items(uris, limit=10))
        for batch in batches[:-1]:
            assert len(batch) == 10
        assert len(batches[-1]) == len(uris) % 10 if len(uris) % 10 != 0 else 10

    def test_generate_many_url(self, uris: list[URI]):
        url = URL("https://api.example.com/resources")
        uris = list(map(str, uris[:10]))

        url = RemoteEndpoints._generate_batch_url(url, uris)
        assert url.query["ids"] == ",".join(uris)


class TestGetSingleEndpoints(RemoteEndpointsTester):
    @pytest.fixture
    def model(self, handler: RequestHandler) -> RemoteEndpoints:
        return RemoteGetSingleEndpoints[Authoriser, SimpleURI, MockRemoteResource](
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
    def mock_create(self, response: dict[str, Any]) -> Generator[Mock, None, None]:
        with patch.object(RemoteEndpoints, "create") as mock_create:
            yield mock_create
            mock_create.assert_called_once_with(response)

    @pytest.mark.parametrize("converter", URI_TYPE_CONVERTERS.values(), ids=URI_TYPE_CONVERTERS.keys())
    async def test_get_on_uri(
            self, model: RemoteEndpoints, uri: URI, mock_get: Mock, mock_create: Mock, converter: Callable[[URI], Any]
    ):
        await model.get(converter(uri))


class TestGetManyEndpoints(RemoteEndpointsTester):
    class MockGetManyEndpoints(RemoteGetManyEndpoints[Authoriser, SimpleURI, MockRemoteResource]):
        _many_url = URL(f"https://api.example.com/{MockRemoteResource.type}s")
        _many_path = "items"
        _many_limit = 10

    @pytest.fixture
    def model(self, handler: RequestHandler) -> RemoteGetManyEndpoints:
        return self.MockGetManyEndpoints(handler=handler)

    @pytest.fixture
    def mock_extend_items_from_response(self, uris: list[URI], limit: int) -> Generator[Mock, None, None]:
        expected = math.ceil(len(uris) / limit)

        with patch.object(
                RemoteGetManyEndpoints, "_extend_items_from_response"
        ) as mock_extend_items_from_response:
            yield mock_extend_items_from_response
            assert mock_extend_items_from_response.call_count == expected

    @pytest.mark.parametrize("converter", URI_TYPE_CONVERTERS.values(), ids=URI_TYPE_CONVERTERS.keys())
    async def test_get_many(
            self,
            model: RemoteGetManyEndpoints,
            uris: list[URI],
            limit: int,
            mock_get: Mock,
            mock_batch_items: Mock,
            mock_extend_items_from_response: Mock,
            converter: Callable[[URI], Any],
    ):
        await model.get_many(list(map(converter, uris)), limit=limit)


class TestGetSavedEndpoints(RemoteEndpointsTester):
    class MockGetSavedEndpoints(RemoteGetSavedEndpoints[Authoriser, SimpleURI, MockRemoteResource]):
        _saved_url = URL("https://api.example.com/me")
        _saved_path = "items"

        source = MockRemoteResource.source
        type = MockRemoteResource.type

    @pytest.fixture
    def model(self, handler: RequestHandler) -> RemoteGetSavedEndpoints:
        return self.MockGetSavedEndpoints(handler=handler)

    async def test_get_saved(self, handler: RequestHandler, uri: URI, faker: Faker):
        model = self.MockGetSavedEndpoints(handler=handler)
        limit = faker.random_int(1, 100)
        offset = faker.random_int(1, 100)

        with (
            patch.object(
                RemoteGetSavedEndpoints, "_create_saved_items_cursor", return_value=ItemsCursor(current=uri.api_url)
            ) as mock_create_cursor,
            patch.object(RemoteGetSavedEndpoints, "_extend_items_from_cursor") as mock_extend_items,
        ):
            await model.get_saved(limit=limit, offset=offset)

            mock_create_cursor.assert_called_once_with(
                self.MockGetSavedEndpoints._saved_url, limit=limit, offset=offset
            )
            mock_extend_items.assert_called_once_with(
                items=[],
                cursor=mock_create_cursor.return_value,
                path=self.MockGetSavedEndpoints._saved_path,
                kind=self.MockGetSavedEndpoints.type,
            )


class TestMutableSavedEndpoints(RemoteEndpointsTester):
    class MockMutableSavedEndpoints(RemoteMutableSavedEndpoints[Authoriser, SimpleURI, MockRemoteResource]):
        _saved_url = URL("https://api.example.com/me")
        _saved_path = "items"

    @pytest.fixture
    def model(self, handler: RequestHandler) -> RemoteMutableSavedEndpoints:
        return self.MockMutableSavedEndpoints(handler=handler)

    async def test_add_saved(
            self,
            model: RemoteMutableSavedEndpoints,
            uris: list[URI],
            limit: int,
            mock_batch_items: Mock,
            mock_put: Mock,
            faker: Faker,
    ):
        await model.add_saved(list(map(self._convert_uri_to_random_input_type, uris)), limit=limit)

    async def test_remove_saved(
            self,
            model: RemoteMutableSavedEndpoints,
            uris: list[URI],
            limit: int,
            mock_batch_items: Mock,
            mock_delete: Mock,
            faker: Faker,
    ):
        await model.remove_saved(list(map(self._convert_uri_to_random_input_type, uris)), limit=limit)


class TestMutableCollectionEndpoints(RemoteEndpointsTester):
    @pytest.fixture
    def model(self, handler: RequestHandler) -> RemoteMutableCollectionEndpoints:
        return RemoteMutableCollectionEndpoints[Authoriser, SimpleURI, MockRemoteResource](
            handler=handler
        )

    @pytest.mark.parametrize("converter", URI_TYPE_CONVERTERS.values(), ids=URI_TYPE_CONVERTERS.keys())
    async def test_extend(
            self,
            model: RemoteMutableCollectionEndpoints,
            uri: URI,
            uris: list[URI],
            limit: int,
            mock_batch_items: Mock,
            mock_post: Mock,
            faker: Faker,
            converter: Callable[[URI], Any],
    ):
        url = converter(uri)
        await model.extend(url, list(map(self._convert_uri_to_random_input_type, uris)), limit=limit)

    @pytest.mark.parametrize("converter", URI_TYPE_CONVERTERS.values(), ids=URI_TYPE_CONVERTERS.keys())
    async def test_remove(
            self,
            model: RemoteMutableCollectionEndpoints,
            uri: URI,
            uris: list[URI],
            limit: int,
            mock_batch_items: Mock,
            mock_delete: Mock,
            faker: Faker,
            converter: Callable[[URI], Any],
    ):
        url = converter(uri)
        await model.remove(url, list(map(self._convert_uri_to_random_input_type, uris)), limit=limit)
