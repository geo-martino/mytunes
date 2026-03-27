from typing import Any

from musify.processors.base import DynamicProcessor, dynamicprocessormethod


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
class TestDynamicProcessor(DynamicProcessor):
    __test__ = False

    @dynamicprocessormethod
    def processor_1(self):
        return 1

    @dynamicprocessormethod("processor_2_alt")
    def processor_2(self):
        return 2

    @dynamicprocessormethod("processor_3_alternative", "processor_extra")
    def processor_3(self):
        return 3

    def as_dict(self) -> dict[str, Any]:
        return {}


def test_dynamic_processor():
    obj = TestDynamicProcessor()
    assert obj.__processormethods__ == {
        "processor_1", "processor_2", "processor_2_alt", "processor_extra", "processor_3", "processor_3_alternative"
    }
    obj._processor_name = "processor_1"
    assert obj._processor_method == obj.processor_1
    assert obj() == 1

    obj._processor_name = "processor_2_alt"
    assert obj() == 2

    obj._processor_name = "processor_extra"
    assert obj._processor_method == obj.processor_3
    assert obj() == 3
