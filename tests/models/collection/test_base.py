import math

import pytest
from faker import Faker
from pydantic import TypeAdapter, ValidationError
from yarl import URL

from musify.exception import MusifyValueError
from musify.models.collection import PageCursor
from tests.models.testers import BaseModelTester


class TestPageCursor(BaseModelTester):
    @pytest.fixture
    def model(self, faker: Faker) -> PageCursor:
        return PageCursor(
            url="https://api.musify.com/v1/albums?offset=0&limit=50",
        )

    def test_from_url(self, faker: Faker):
        url = faker.url()
        model = PageCursor.model_validate(faker.random_element((url, URL(url))))
        assert model.url == URL(url)

    def test_get_params_from_url(self, faker: Faker):
        limit = faker.random_int()
        offset = faker.random_int()
        url = URL(faker.url()).update_query(limit=limit, offset=offset)

        model = PageCursor(url=url)
        assert model.url == url
        assert model.limit == limit
        assert model.offset == offset

    def test_keeps_params_if_provided(self, faker: Faker):
        limit = faker.random_int()
        offset = faker.random_int()
        url = URL(faker.url()).update_query(offset=faker.random_int(), limit=faker.random_int())

        model = PageCursor(url=url, limit=limit, offset=offset)
        assert model.url == url.update_query(limit=limit, offset=offset)
        assert model.limit == limit != int(url.query["limit"])
        assert model.offset == offset != int(url.query["offset"])

        model.url = url  # force revalidation
        assert model.url == url.update_query(limit=limit, offset=offset)
        assert model.limit == limit != int(url.query["limit"])
        assert model.offset == offset != int(url.query["offset"])

    def test_set_params_to_current_url(self, faker: Faker):
        limit = faker.random_int()
        offset = faker.random_int()
        url = URL(faker.url())

        model = PageCursor(url=url, limit=limit, offset=offset)
        assert model.url == url.update_query(limit=limit, offset=offset)
        assert model.limit == limit
        assert model.offset == offset

        model.url = url  # force revalidation
        assert model.url == url.update_query(limit=limit, offset=offset)
        assert model.limit == limit
        assert model.offset == offset

        model.limit += faker.random_int()
        model.offset += faker.random_int()
        assert model.url == url.update_query(limit=model.limit, offset=model.offset)

    def test_set_offset_and_after_fails(self, faker: Faker):
        with pytest.raises(ValidationError, match="Cannot have both offset and after set in the same cursor"):
            PageCursor(url=faker.url(), offset=faker.random_int(), after=faker.pystr())

    def test_drop_limit_from_current_url(self, model: PageCursor, faker: Faker):
        model.limit = faker.random_int()
        assert "limit" in model.url.query

        model.limit = 0
        assert "limit" not in model.url.query

    def test_previous_fails(self, model: PageCursor, faker: Faker):
        field_names = {"offset", "limit"}
        model.offset = None
        model.limit = None

        while len(field_names) < 1:
            field_name = field_names.pop()
            setattr(model, field_name, faker.random_int())

            with pytest.raises(MusifyValueError, match="Cannot generate next URL without offset and limit"):
                assert model.previous

    def test_previous(self, model: PageCursor, faker: Faker):
        model.limit = faker.random_int()
        model.offset = model.limit + faker.random_int()

        prev_cursor = model.previous
        assert prev_cursor.url == model.url.update_query(offset=model.offset - model.limit)
        assert prev_cursor.offset == model.offset - model.limit
        assert prev_cursor.limit == model.limit

        model.offset = 0
        assert model.previous is None

    def test_next_fails_on_offset(self, model: PageCursor, faker: Faker):
        field_names = {"offset", "limit", "total"}
        model.offset = None
        model.after = None
        model.limit = None
        model.total = None

        while len(field_names) < 1:
            field_name = field_names.pop()
            setattr(model, field_name, faker.random_int())

            with pytest.raises(MusifyValueError, match="Cannot generate next URL without offset, limit and total"):
                assert model.next

    def test_next_from_offset(self, faker: Faker):
        offset = faker.random_int()
        limit = faker.random_int(1, offset // 5)
        total = offset + limit + faker.random_int()

        url = URL(faker.url()).with_query(offset=offset, limit=limit)
        next_url = url.update_query(offset=offset + limit)

        model = PageCursor(url=url, offset=offset, limit=limit, total=total)
        next_cursor = model.next
        assert next_cursor.next is not model
        assert next_cursor.url == next_url
        assert next_cursor.offset == offset + limit
        assert next_cursor.after is None
        assert next_cursor.limit == limit
        assert next_cursor.total == total

    def test_next_from_offset_skips_if_no_items(self, faker: Faker):
        total = faker.random_int()

        model = PageCursor(url=URL(faker.url()), offset=total + 1, limit=faker.random_int(), total=total)
        assert model.next is None

        model = PageCursor(url=URL(faker.url()), offset=0, limit=0, total=0)
        assert model.next is None

    def test_next_from_after(self, model: PageCursor, faker: Faker):
        after = faker.pystr()
        limit = faker.random_int()
        total = limit + faker.random_int()

        url = URL(faker.url()).with_query(after=faker.pystr(), limit=limit)
        next_url = url.update_query(after=after, limit=limit)

        model = PageCursor(url=url, after=after, limit=limit, total=total)
        next_cursor = model.next
        assert next_cursor.next is not model
        assert next_cursor.url == next_url
        assert next_cursor.offset is None
        assert next_cursor.after is None
        assert next_cursor.limit == limit
        assert next_cursor.total == total

        # ignores offset, limit and total because after is the primary pagination method in this case
        assert next_cursor.next is None

    def test_next_from_source(self, faker: Faker):
        offset = faker.random_int()
        after = faker.pystr()
        limit = faker.random_int()
        total = offset + limit + faker.random_int()

        url = URL(faker.url())
        next_url = url.update_query(offset=faker.random_int())

        model = PageCursor(url=url, next=next_url, offset=offset, limit=limit, total=total)
        next_cursor = model.next
        assert next_cursor is not model
        assert next_cursor.url == next_url.update_query(limit=limit)

        model = PageCursor(url=url, next=next_url, after=after)
        next_cursor = model.next
        assert next_cursor is not model
        assert next_cursor.url == next_url

    def test_next_is_current(self, faker: Faker):
        url = URL(faker.url())

        model = PageCursor(url=url, next_is_current=True)
        next_cursor = model.next
        assert next_cursor is not model
        assert next_cursor.url == url

    def test_iter_next(self, model: PageCursor, faker: Faker):
        model.limit = faker.random_int(10, 100)
        model.offset = faker.random_int(100, 1000)
        model.total = model.offset + faker.random_int(100, 1000)

        pages = math.ceil((model.total - model.offset) / model.limit)
        expected_urls = [model.url.update_query(offset=model.offset + (model.limit * i)) for i in range(1, pages)]

        result = list(model.iter_next)
        assert int(result[0].offset) == model.offset + model.limit
        assert int(result[-1].offset) <= model.total

        for cursor, next_cursor in zip(result, result[1:]):
            assert cursor.next == next_cursor
            assert cursor == next_cursor.previous

        assert [cursor.url for cursor in result] == expected_urls
        assert [cursor.offset for cursor in result] == [model.offset + (model.limit * i) for i in range(1, pages)]

    def test_reset(self, model: PageCursor, faker: Faker):
        model.limit = faker.random_int(1, 100)
        model.offset = faker.random_int(100, 1000)
        assert model.url.query["offset"] == str(model.offset)

        model.reset()
        assert model.offset == 0
        assert "offset" not in model.url.query
