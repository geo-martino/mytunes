import random
from collections.abc import Generator
from copy import copy
from typing import Self, final, ClassVar, Any
from unittest.mock import patch, Mock, PropertyMock

import math
import pytest
from faker import Faker
from pydantic import AliasPath, AliasChoices
from yarl import URL

from musify.models.cursors import PageCursor, IterablePageCursor, IndexCursor, KeyCursor, UrlCursor, InitialCursor
from musify.models.exception import CursorError
from tests.models.testers import BaseModelTester


@final
class MockPageCursor(PageCursor):
    __final__ = True

    source: ClassVar[str] = "test"

    param: str | None = None

    @property
    def next(self) -> Self:
        return self


class TestPageCursor(BaseModelTester):

    @pytest.fixture
    def model(self, faker: Faker) -> PageCursor:
        return MockPageCursor(url=faker.url())

    def test_from_url(self, faker: Faker):
        url = faker.url()
        model = MockPageCursor.model_validate(faker.random_element((url, URL(url))))
        assert model.url == URL(url)

    def test_set_param_value_from_url(self, faker: Faker):
        expected = faker.random_int()
        field_name = "param"
        param_key = "id"

        url = URL(faker.url()).update_query({param_key: expected})
        data = {faker.random_element(("href", "url")): url}

        MockPageCursor._set_param_value_from_url(data=data, field_name=field_name, param_key=param_key)
        assert data[field_name] == str(expected)

    def test_set_param_value_from_url_skips_on_no_url(self, faker: Faker):
        data = {}
        MockPageCursor._set_param_value_from_url(data=data, field_name="param", param_key="id")
        assert data == {}

        data = {faker.random_element(("href", "url")): None}
        expected = copy(data)
        MockPageCursor._set_param_value_from_url(data=data, field_name="param", param_key="id")
        assert data == expected

    def test_set_param_value_from_url_skips_on_invalid_url(self, faker: Faker):
        field_name = "param"
        param_key = "id"

        url = faker.random_int()
        data = {faker.random_element(("href", "url")): url}
        expected = copy(data)

        MockPageCursor._set_param_value_from_url(data=data, field_name=field_name, param_key=param_key)
        assert data == expected

    def test_set_param_value_from_url_skips_on_value_set(self, faker: Faker):
        expected = faker.random_int()
        field_name = "param"
        param_key = "id"

        url = URL(faker.url()).update_query({param_key: faker.random_int()})
        data = {faker.random_element(("href", "url")): url, field_name: expected}

        MockPageCursor._set_param_value_from_url(data=data, field_name=field_name, param_key=param_key)
        assert data[field_name] == expected

    def test_set_param_value_to_url_adds_param(self, model: PageCursor, faker: Faker):
        expected = faker.random_int()
        param_key = "id"

        model.url = model.url.with_query({})
        assert param_key not in model.url.query

        model._set_param_value_to_url(key=param_key, value=expected)
        assert model.url.query.get(param_key) == str(expected)

    def test_set_param_value_to_url_removes_param(self, model: PageCursor, faker: Faker):
        param_key = "id"

        model.url = model.url.with_query({param_key: faker.pystr()})
        assert param_key in model.url.query

        model._set_param_value_to_url(key=param_key, value="")
        assert param_key not in model.url.query

    def test_set_param_value_to_url_skips(self, model: PageCursor, faker: Faker):
        param_value = faker.random_int()
        param_key = "id"

        model.url = model.url.with_query({param_key: param_value})
        expected = model.url

        model._set_param_value_to_url(key=param_key, value=param_value)
        assert model.url == expected

        model._set_param_value_to_url(key=param_key, value=str(param_value))
        assert model.url == expected

    @pytest.fixture
    def cursor_data(self, faker: Faker) -> dict[str, str]:
        return {"url": faker.url(), "param": faker.pystr()}

    def test_get_cursor_from_response_on_key(self, model: PageCursor, cursor_data: dict[str, Any], faker: Faker):
        key = faker.random_element((faker.pystr(), None))  # ignores key on str or None
        assert model.get_cursor_from_response(cursor_data, key) == MockPageCursor(**cursor_data)

    def test_get_cursor_from_response_on_path(self, model: PageCursor, cursor_data: dict[str, Any], faker: Faker):
        path = AliasPath("item", "data", "nested", "items")
        data = faker.pydict() | {"item": {"id": faker.random_int(), "data": cursor_data}}
        assert model.get_cursor_from_response(data, path) == MockPageCursor(**cursor_data)

    def test_get_cursor_from_response_on_choices(self, model: PageCursor, cursor_data: dict[str, Any], faker: Faker):
        choices = AliasChoices(
            "item",
            AliasPath("item", "data"),
            AliasPath("item", "data", "nested", "items", "unknown"),
            AliasPath("item", "data", "nested", "items"),  # should pass on this one
            "unknown",
        )
        data = faker.pydict() | {"item": {"id": faker.random_int(), "data": cursor_data}}
        assert model.get_cursor_from_response(data, choices) == MockPageCursor(**cursor_data)


class TestIterablePageCursor(BaseModelTester):

    @pytest.fixture
    @patch.multiple(
        IterablePageCursor,
        __abstractmethods__=set(),
        next=Mock(),
    )
    def model(self, faker: Faker) -> IterablePageCursor:
        return IterablePageCursor(url=faker.url())

    @pytest.fixture
    def mock_next(self) -> Generator[Mock, None, None]:
        with patch.object(IterablePageCursor, "next", new_callable=PropertyMock) as mock_next:
            yield mock_next

    def test_iter_pages_fails(self, model: IterablePageCursor, mock_next: Mock, faker: Faker):
        mock_next.return_value = model
        with pytest.raises(CursorError, match="The next cursor is the same as the current cursor"):
            assert list(model.iter_pages)

    def test_iter_pages(self, model: IterablePageCursor, mock_next: Mock, faker: Faker):
        mock_next.return_value = None
        # can't find a way to test an actual iterable set of pages
        # just check that it doesn't iter when no next page is available
        assert not list(model.iter_pages)


class TestIndexCursor(BaseModelTester):
    @pytest.fixture
    def model(self, faker: Faker) -> IndexCursor:
        offset = faker.random_int()
        limit = faker.random_int(1, offset // 5) if offset / 5 > 1 else 1
        total = offset + limit * 5

        return IndexCursor(url=faker.url(), offset=offset, limit=limit, total=total)

    def test_set_params_from_url(self, faker: Faker):
        limit = faker.random_int()
        offset = faker.random_int()
        url = URL(faker.url()).update_query(limit=limit, offset=offset)

        model = IndexCursor(url=url, total=faker.random_int())
        assert model.url == url
        assert model.limit == limit
        assert model.offset == offset

        # overwrites params on given url if limit and offset are set on model
        model.url = url.update_query(limit=faker.random_int(), offset=faker.random_int())
        assert model.url == url
        assert model.limit == limit
        assert model.offset == offset

    def test_set_params_to_url(self, faker: Faker):
        limit = faker.random_int()
        offset = faker.random_int()
        url = URL(faker.url())

        model = IndexCursor(url=url, limit=limit, offset=offset, total=faker.random_int())
        assert model.url == url.update_query(limit=limit, offset=offset)
        assert model.limit == limit
        assert model.offset == offset

        # updates url on model
        model.limit += faker.random_int()
        model.offset += faker.random_int()
        assert model.url == url.update_query(limit=model.limit, offset=model.offset)

    def test_previous(self, model: IndexCursor):
        prev_cursor = model.previous
        assert prev_cursor.url == model.url.update_query(offset=model.offset - model.limit)
        assert prev_cursor.offset == model.offset - model.limit
        assert prev_cursor.limit == model.limit

    def test_previous_skips_on_0_offset(self, model: IndexCursor):
        assert model.previous is not None
        model.offset = 0
        assert model.previous is None

    def test_next(self, model: IndexCursor):
        expected_url = model.url.update_query(offset=model.offset + model.limit)

        next_cursor = model.next
        assert next_cursor.url == expected_url
        assert next_cursor.offset == model.offset + model.limit
        assert next_cursor.limit == model.limit
        assert next_cursor.total == model.total
        assert next_cursor.next is not model

    def test_next_skips_on_offset_over_total(self, model: IndexCursor):
        assert model.next is not None
        model.offset = model.total + 1
        assert model.next is None

    def test_next_skips_on_0_total(self, model: IndexCursor):
        assert model.next is not None
        model.total = 0
        assert model.next is None

    def test_iter_pages(self, model: IndexCursor):
        pages = math.ceil((model.total - model.offset) / model.limit)
        expected_offsets = [model.offset + (model.limit * i) for i in range(1, pages)]
        expected_urls = [model.url.update_query(offset=offset) for offset in expected_offsets]

        result = list(model.iter_pages)
        assert int(result[0].offset) == model.offset + model.limit
        assert int(result[-1].offset) <= model.total

        for cursor, next_cursor in zip(result, result[1:]):
            assert cursor.next == next_cursor
            assert cursor == next_cursor.previous

        assert [cursor.url for cursor in result] == expected_urls
        assert [cursor.offset for cursor in result] == expected_offsets

    def test_reset(self, model: IndexCursor, faker: Faker):
        assert model.url.query["offset"] == str(model.offset)

        model.reset(0)
        assert model.offset == 0
        assert model.url.query.get("offset", "0") == "0"

        offset = faker.random_int()
        model.reset(offset)
        assert model.offset == offset
        assert model.url.query.get("offset", "0") == str(offset)

    def test_sort_responses(self, model: IndexCursor, faker: Faker):
        limit = faker.random_int()
        total = faker.random_int()
        url = URL(faker.url())
        expected_responses = [
            {"url": url, "offset": i, "limit": limit, "total": total}
            for i in range(faker.random_int(3, 10))
        ]

        responses = expected_responses.copy()
        while responses == expected_responses:
            random.shuffle(responses)

        cursors = [IndexCursor(**response) for response in responses]
        expected_cursors = [IndexCursor(**response) for response in expected_responses]
        iter_cursors = iter(cursors)

        with patch.object(
                IndexCursor, "get_cursor_from_response", side_effect=lambda *_, **__: next(iter_cursors)
        ) as mock_get_cursor:
            result = IndexCursor.sort_responses(responses=responses, path="id")
            assert responses == expected_responses
            assert result == expected_cursors

            assert mock_get_cursor.call_count == len(responses)


class TestKeyCursor(BaseModelTester):
    @pytest.fixture
    def model(self, faker: Faker) -> KeyCursor:
        return KeyCursor(url=faker.url(), before=faker.pystr(), after=faker.pystr())

    def test_previous(self, model: KeyCursor):
        expected_url = model.url.update_query(after=model.before)

        prev_cursor = model.previous
        assert prev_cursor.url == expected_url
        assert prev_cursor.before is None
        assert prev_cursor.after is None

    def test_previous_skips_on_no_before(self, model: KeyCursor):
        assert model.previous is not None
        model.before = None
        assert model.previous is None

    def test_next(self, model: KeyCursor):
        expected_url = model.url.update_query(after=model.after)

        next_cursor = model.next
        assert next_cursor.url == expected_url
        assert next_cursor.before is None
        assert next_cursor.after is None

    def test_next_skips_on_no_after(self, model: KeyCursor):
        assert model.next is not None
        model.after = None
        assert model.next is None


class TestUrlCursor(BaseModelTester):
    @pytest.fixture
    def model(self, faker: Faker) -> UrlCursor:
        return UrlCursor(url=faker.url(), previous=faker.url(), next=faker.url())

    def test_previous(self, model: UrlCursor):

        prev_cursor = model.previous
        assert prev_cursor.url == model.previous_url
        assert prev_cursor.previous_url is None
        assert prev_cursor.next_url == model.url

    def test_previous_skips_on_no_url(self, model: UrlCursor):
        assert model.previous is not None
        model.previous_url = None
        assert model.previous is None

    def test_next(self, model: UrlCursor):
        next_cursor = model.next
        assert next_cursor.url == model.next_url
        assert next_cursor.previous_url == model.url
        assert next_cursor.next_url is None

    def test_next_skips_on_no_url(self, model: UrlCursor):
        assert model.next is not None
        model.next_url = None
        assert model.next is None


class TestInitialCursor(BaseModelTester):
    @pytest.fixture
    def model(self, faker: Faker) -> InitialCursor:
        return InitialCursor(url=faker.url())

    def test_next(self, model: InitialCursor):
        assert model.next == model
        assert model.next is not model
