from abc import ABCMeta, abstractmethod
from copy import deepcopy
from pathlib import Path
from random import shuffle, choice

import pytest
from faker import Faker

from musify.models.properties.file import _IsFile
from musify.processors_new.filters import Filter, FilterValues, FilterPaths, FilterIncludeExclude
from tests.models.testers import MusifyModelTester


class FilterTester(MusifyModelTester, metaclass=ABCMeta):
    """Base class for testing filters"""
    @abstractmethod
    def test_equality(self, model: Filter):
        raise NotImplementedError

    @abstractmethod
    def test_check(self, model: Filter, faker: Faker):
        raise NotImplementedError


class TestFilterValues(FilterTester):

    @pytest.fixture
    def model(self, faker: Faker) -> FilterValues:
        values = {"".join(faker.random_letters(faker.random_int(30, 50))) for _ in range(20)}
        return FilterValues(values=values)

    def test_equality(self, model: FilterValues):
        assert model == deepcopy(model)

        new_filter = model.__class__(values=deepcopy(model.values))
        assert model == new_filter

        new_filter.values = set(deepcopy(list(model.values)[len(model.values) // 2]))
        assert model != new_filter

    def test_check(self, model: FilterValues, faker: Faker):
        values = list(model.values)
        assert all(model.check(value) for value in values)

        values_missing = {
            "".join(faker.random_letters(faker.random_int(30, 50))) for _ in range(10)
        } - model.values
        assert not any(model.check(value) for value in values_missing)

    def test_apply_on_empty_filter(self, model: FilterValues):
        assert model.__class__().apply(model.values) == list(model.values)

    def test_apply(self, model: FilterValues):
        values = list(model.values)
        expected = values.copy()
        shuffle(expected)

        filter_ = FilterValues(values=model.values)
        assert filter_.apply(values[:10]) == values[:10]


class TestFilterPaths(TestFilterValues):

    @pytest.fixture
    def model(self, faker: Faker) -> FilterPaths:
        values = {faker.file_path() for _ in range(20)}
        return FilterPaths(values=values)

    def test_extract_values(self, model: FilterPaths, faker: Faker):
        expected = [faker.file_path() for _ in range(10)]
        values = [choice([value, Path(value), _IsFile(path=Path(value))]) for value in expected]
        # noinspection PyTypeChecker
        assert FilterPaths(values=values).values == set(expected)


class TestFilterIncludeExclude(FilterTester):

    @pytest.fixture
    def model(self, faker: Faker) -> FilterIncludeExclude:
        include_values = {"".join(faker.random_letters(faker.random_int(30, 50))) for _ in range(20)}
        exclude_values = {
            "".join(faker.random_letters(faker.random_int(30, 50))) for _ in range(20)
        } - include_values

        return FilterIncludeExclude(
            include=FilterValues(values=include_values),
            exclude=FilterValues(values=set(list(include_values)[:10] + list(exclude_values))),
        )

    def test_equality(self, model: FilterIncludeExclude):
        new_filter = FilterIncludeExclude(include=deepcopy(model.include), exclude=deepcopy(model.exclude))
        assert model == new_filter

        new_filter.include = deepcopy(model.exclude)
        new_filter.exclude = deepcopy(model.include)
        assert model != new_filter

    def test_check(self, model: Filter, faker: Faker):
        value = next(value for value in model.include.values if value not in model.exclude.values)
        assert model.check(value)

        value = next(value for value in model.include.values if value in model.exclude.values)
        assert not model.check(value)

        value = next(value for value in model.exclude.values)
        assert not model.check(value)

    def test_apply(self, model: FilterIncludeExclude):
        expected = [value for value in model.include.values if value not in model.exclude.values]
        # there should be some overlap between include and exclude values
        assert expected != model.include.values

        assert model.apply(model.include.values) == expected
        assert not model.apply(model.exclude.values)
