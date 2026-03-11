import pytest
from faker import Faker
from pydantic import TypeAdapter

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
