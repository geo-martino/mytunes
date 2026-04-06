from copy import deepcopy
from pathlib import Path
from random import shuffle, choice

import pytest
from faker import Faker

from musify._models.properties.file import IsLocalFile
from musify._models.properties.name import HasName
from musify.processors.filters.values import ValueFilter, PathFilter, NameFilter
from tests.processors.filters.testers import FilterTester


class TestValueFilter(FilterTester):

    @pytest.fixture
    def model(self, faker: Faker) -> ValueFilter:
        values = {faker.pystr(30, 50) for _ in range(20)}
        return ValueFilter(values=values)

    def test_from_values(self, model: ValueFilter, faker: Faker):
        values = faker.words()
        assert model.__class__.model_validate(values) == model.__class__(values=set(values))

    def test_equality(self, model: ValueFilter, faker: Faker):
        assert model == deepcopy(model)

        new_filter = model.__class__(values=deepcopy(model.values))
        assert model == new_filter

        new_filter.values = set(deepcopy(list(model.values)[:len(model.values) // 2]))
        assert model != new_filter

    def test_check(self, model: ValueFilter, faker: Faker):
        values = list(model.values)
        assert all(model.check(value) for value in values)

        values_missing = {faker.pystr(30, 50) for _ in range(10)} - model.values
        assert not any(model.check(value) for value in values_missing)

    def test_apply_on_empty_filter(self, model: ValueFilter):
        assert model.__class__().apply(model.values) == list(model.values)

    def test_apply(self, model: ValueFilter):
        values = list(model.values)
        expected = values.copy()
        shuffle(expected)

        filter_ = model.__class__(values=model.values)
        assert filter_.apply(values[:10]) == values[:10]


class TestNameFilter(TestValueFilter):

    @pytest.fixture
    def model(self, faker: Faker) -> NameFilter:
        values = {faker.name() for _ in range(20)}
        return NameFilter(values=values)

    def test_extract_values(self, model: PathFilter, faker: Faker):
        expected = [faker.name() for _ in range(10)]
        values = [choice([value, HasName(name=value)]) for value in expected]
        # noinspection PyTypeChecker
        assert NameFilter(values=values).values == set(expected)


class TestPathFilter(TestValueFilter):

    @pytest.fixture
    def model(self, faker: Faker) -> PathFilter:
        values = {faker.file_path() for _ in range(20)}
        return PathFilter(values=values)

    def test_extract_values(self, model: PathFilter, faker: Faker):
        expected = [faker.file_path() for _ in range(10)]
        values = [choice([value, Path(value), IsLocalFile(path=Path(value))]) for value in expected]
        # noinspection PyTypeChecker
        assert PathFilter(values=values).values == set(expected)
