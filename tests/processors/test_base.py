from random import choice
from typing import final, Annotated

import pytest

from musify.processors import DynamicProcessor, processormethod, ProcessorAttribute
from tests.models.testers import BaseModelTester


def test_dynamic_processor_method_decorator():
    @processormethod
    def test_1():
        return 1

    assert isinstance(test_1, processormethod)
    assert not test_1.alternative_names
    assert test_1() == 1

    @processormethod("alt_1", "alt_2")
    def test_2():
        return 2

    assert isinstance(test_2, processormethod)
    assert test_2.alternative_names == ("alt_1", "alt_2")
    assert test_2() == 2


# noinspection PyMissingOrEmptyDocstring
@final
class MockDynamicProcessor(DynamicProcessor):
    __final__ = True
    __test__ = False

    processor_name: Annotated[str | None, ProcessorAttribute()] = f"processor_{choice([1, 2, 3])}"

    @processormethod
    def processor_1(self):
        return 1

    @processormethod("_processor_2_alt")
    def processor_2(self):
        return 2

    @processormethod("processor_3_alternative__", "_ProcessorExtra")
    def processor_3(self):
        return 3


class TestDynamicProcessor(BaseModelTester):
    @pytest.fixture
    def model(self):
        return MockDynamicProcessor()

    def test_collects_and_formats_all_processor_names(self, model: MockDynamicProcessor):
        assert model.__processor_method_map__ == {
            "processor_1": "processor_1",
            "processor_2": "processor_2",
            "_processor_2_alt": "processor_2",
            "processor_3": "processor_3",
            "processor_3_alternative__": "processor_3",
            "_ProcessorExtra": "processor_3",
        }

    def test_gets_processor_method(self, model: MockDynamicProcessor):
        model.processor_name = "processor_1"
        assert model._processor_method == model.processor_1
        assert model._processor_method() == 1

        model.processor_name = "_processor_2_alt"
        assert model._processor_method == model.processor_2
        assert model._processor_method() == 2

        model.processor_name = "_ProcessorExtra"
        assert model._processor_method == model.processor_3
        assert model._processor_method() == 3
