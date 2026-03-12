import math

import pytest
from faker import Faker
from pydantic import TypeAdapter
from yarl import URL

from musify.exception import MusifyValueError
from musify.models.collection import ItemsCursor
from tests.models.testers import BaseModelTester


class TestItemsCursor(BaseModelTester):
    @pytest.fixture
    def model(self, faker: Faker) -> ItemsCursor:
        return ItemsCursor(
            current="https://api.musify.com/v1/albums?offset=0&limit=50",
        )

    def test_from_url(self, model: ItemsCursor):
        assert model == TypeAdapter(ItemsCursor).validate_python(str(model.current))

    def test_do_not_set_limit_to_current_url(self, model: ItemsCursor, faker: Faker):
        model.limit = None
        starting_limit = faker.random_int(1, 100)
        model.current = model.current.with_query(limit=starting_limit)
        assert model.current.query["limit"] == str(starting_limit)

        model.limit = None
        assert model.current.query["limit"] == str(starting_limit)

    def test_set_limit_to_current_url(self, model: ItemsCursor, faker: Faker):
        model.limit = None
        starting_limit = faker.random_int(1, 100)
        model.current = model.current.with_query(limit=starting_limit)
        assert model.current.query["limit"] == str(starting_limit)

        model.limit = starting_limit + 50
        assert model.current.query["limit"] == str(model.limit)

    def test_drop_limit_from_current_url(self, model: ItemsCursor, faker: Faker):
        model.current = model.current.with_query(limit=faker.random_int(1, 100))
        assert "limit" in model.current.query

        model.limit = 0
        assert "limit" not in model.current.query

    def test_do_not_set_offset_to_current_url(self, model: ItemsCursor, faker: Faker):
        model.offset = None
        starting_offset = faker.random_int(1, 100)
        model.current = model.current.with_query(offset=starting_offset)
        assert model.current.query["offset"] == str(starting_offset)

        model.offset = None
        assert model.current.query["offset"] == str(starting_offset)

    def test_set_offset_to_current_url(self, model: ItemsCursor, faker: Faker):
        model.offset = None
        starting_offset = faker.random_int(1, 100)
        model.current = model.current.with_query(offset=starting_offset)
        assert model.current.query["offset"] == str(starting_offset)

        model.offset = starting_offset + 50
        assert model.current.query["offset"] == str(model.offset)

    def test_current_from_next_fails(self, model: ItemsCursor, faker: Faker):
        model.next = None
        model.limit = None

        message = "Cannot generate URL without offset and next URL"
        with pytest.raises(MusifyValueError, match=message):
            assert model._current_from_next

        model.next = URL(faker.url())
        model.limit = None
        with pytest.raises(MusifyValueError, match=message):
            assert model._current_from_next

        model.next = None
        model.limit = faker.random_int()
        with pytest.raises(MusifyValueError, match=message):
            assert model._current_from_next

    def test_current_from_next(self, model: ItemsCursor, faker: Faker):
        model.next = URL(faker.url())
        model.limit = faker.random_int(1, 100)
        model.offset = faker.random_int(1, 100)

        expected = model.next.update_query(limit=model.limit, offset=model.offset)
        assert model._current_from_next == expected

    def test_next_from_current_fails(self, model: ItemsCursor, faker: Faker):
        model.offset = None
        model.limit = None

        message = "Cannot generate URL without offset and limit"
        with pytest.raises(MusifyValueError, match=message):
            assert model._next_from_current

        model.offset = faker.random_int()
        model.limit = None
        with pytest.raises(MusifyValueError, match=message):
            assert model._next_from_current

        model.offset = None
        model.limit = faker.random_int()
        with pytest.raises(MusifyValueError, match=message):
            assert model._next_from_current

    def test_next_from_current(self, model: ItemsCursor, faker: Faker):
        model.limit = faker.random_int(1, 100)
        model.offset = faker.random_int()

        expected = model.current.update_query(limit=model.limit, offset=model.offset + model.limit)
        assert model._next_from_current == expected

    def test_iter_next(self, model: ItemsCursor, faker: Faker):
        model.limit = faker.random_int(10, 100)
        model.offset = faker.random_int(100, 1000)
        model.total = model.offset + faker.random_int(100, 1000)

        pages = math.ceil((model.total - model.offset) / model.limit)
        expected_urls = [model.current.update_query(offset=model.offset + (model.limit * i)) for i in range(1, pages)]

        result = list(model.iter_next)
        assert int(result[0].offset) == model.offset + model.limit
        assert int(result[-1].offset) <= model.total

        for cursor, next_cursor in zip(result, result[1:] + [None]):
            if next_cursor is not None:
                assert cursor.next == next_cursor.current
            else:
                assert cursor.next is None

        assert [cursor.current for cursor in result] == expected_urls
        assert [cursor.next for cursor in result] == expected_urls[1:] + [None]
        assert [cursor.offset for cursor in result] == [model.offset + (model.limit * i) for i in range(1, pages)]

    def test_reset(self, model: ItemsCursor, faker: Faker):
        model.limit = faker.random_int(1, 100)
        model.offset = faker.random_int(100, 1000)
        model.next = model.current.with_query(offset=model.offset + model.limit)
        model.previous = model.current.with_query(offset=model.offset - model.limit)

        model.reset()
        assert model.previous is None
        assert model.next is None
        assert model.offset == 0
        assert model.current.query["offset"] == str(model.offset)
