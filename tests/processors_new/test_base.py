from random import choice

import pytest

from musify.processors_new import DynamicProcessor, dynamicprocessormethod
from tests.models.testers import MusifyModelTester


def test_dynamic_processor_method_decorator():
    @dynamicprocessormethod
    def test_1():
        return 1

    assert isinstance(test_1, dynamicprocessormethod)
    assert not test_1.alternative_names
    assert test_1() == 1

    @dynamicprocessormethod("alt_1", "alt_2")
    def test_2():
        return 2

    assert isinstance(test_2, dynamicprocessormethod)
    assert test_2.alternative_names == ("alt_1", "alt_2")
    assert test_2() == 2


# noinspection PyMissingOrEmptyDocstring
class MockDynamicProcessor(DynamicProcessor):
    __test__ = False

    processor_name: str | None = f"processor_{choice([1, 2, 3])}"

    @property
    def _processor_name(self) -> str:
        return self.processor_name

    @dynamicprocessormethod
    def processor_1(self):
        return 1

    @dynamicprocessormethod("_processor_2_alt")
    def processor_2(self):
        return 2

    @dynamicprocessormethod("processor_3_alternative__", "_ProcessorExtra")
    def processor_3(self):
        return 3


class TestDynamicProcessor(MusifyModelTester):
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
        assert model() == 1

        model.processor_name = "_processor_2_alt"
        assert model._processor_method == model.processor_2
        assert model() == 2

        model.processor_name = "_ProcessorExtra"
        assert model._processor_method == model.processor_3
        assert model() == 3
