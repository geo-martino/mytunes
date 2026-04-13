from abc import ABCMeta, abstractmethod

from faker import Faker
from mytunes.processors.filters import Filter
from tests.testers import BaseModelTester


class FilterTester(BaseModelTester, metaclass=ABCMeta):
    """Base class for testing filters"""
    @abstractmethod
    def test_equality(self, model: Filter, faker: Faker):
        raise NotImplementedError

    @abstractmethod
    def test_check(self, model: Filter, faker: Faker):
        raise NotImplementedError
