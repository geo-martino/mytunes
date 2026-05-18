"""
Processor making comparisons between objects and data types.
"""
import inspect
import re
from collections.abc import Sequence
from contextlib import suppress
from datetime import datetime
from functools import cached_property
from types import NoneType
from typing import Any, Self, Annotated, get_type_hints, get_args, get_origin, Union, final

from pydantic import Field, TypeAdapter, model_validator, ValidationError
from pydantic.alias_generators import to_snake
from pydantic.fields import FieldInfo
from typing_inspection.introspection import is_union_origin
from typing_inspection.typing_objects import is_typevar

from mytunes._types import LowerSnakeCase, Number
from mytunes.core.properties.name import HasName
from mytunes.core.sequence import UniqueSequence
from mytunes.exception import MyTunesTypeError
from mytunes.processors.time import TimeMapper
from ._base.dynamic import DynamicProcessor, ProcessorAttribute, processormethod
from ._types import _ATTRIBUTE_FIELD_MAP, _ATTRIBUTE_FIELD_TYPE, \
    ItemCollection
from .._base.attribute import AttributeModel


@final
class Comparer(DynamicProcessor):
    """
    Compares an item or object with another item, object or a given set of expected values to find a match.

    The expected value given will be cast to the appropriate type based on the field being compared
    according to the type hints of the selected field.
    Attempts will be made to convert the expected value to the appropriate type based on Pydantic
    field type conversion rules.
    """
    __final__ = True

    condition: Annotated[
        LowerSnakeCase,
        ProcessorAttribute(cleaner=lambda x: to_snake(x).replace(" ", "_").strip("_"))
    ] = Field(
        description="The condition to match on.",
    )
    expected: Any = Field(
        description="Expected value/s to match on.",
        default=None,
    )
    field: Union[_ATTRIBUTE_FIELD_TYPE, NoneType] = Field(
        description="The field to match on.",
        default=None,
    )
    reference_required: bool = Field(
        description=(
            "When True, a reference object must be passed to the ``compare`` method. "
            "When False, reference files given to the ``compare`` method will be ignored. "
            "An exception will be raised if this is True and reference object is not passed."
        ),
        default=False,
    )

    @property
    def _field_type(self) -> type:
        if self.field is None:
            return self._extract_type_from_annotation(NoneType)

        match _ATTRIBUTE_FIELD_MAP[self.field].get_field_info(self.field):
            case FieldInfo() as field:
                annotation = field.annotation
            case property() as prop:
                annotation = get_type_hints(prop.fget, include_extras=True)["return"]
            case annotation:
                raise MyTunesTypeError(f"Unknown field type: {annotation}")

        return self._extract_type_from_annotation(annotation)

    @property
    def _actual_type(self) -> type:
        annotation = get_type_hints(self._processor_method.func, include_extras=True)["actual"]
        return self._extract_type_from_annotation(annotation)

    @property
    def _expected_type(self) -> type:
        annotation = get_type_hints(self._processor_method.func, include_extras=True)
        if "expected" not in annotation:  # doesn't take an expected value
            return NoneType

        return self._extract_type_from_annotation(annotation["expected"])

    @staticmethod
    def _extract_type_from_annotation(annotation) -> type:
        origin = get_origin(annotation)
        if is_union_origin(origin):
            types = get_args(annotation)
            types = [t for t in types if t is not NoneType]
            annotation_type = types[0] if len(types) == 1 else Union[tuple(types)]
        else:
            annotation_type = annotation

        return annotation_type

    # noinspection PyCallingNonCallable
    def _clear_cache(self) -> Self:
        # additional cache clears necessary
        with suppress(AttributeError):
            del self._expected_args

        return super()._clear_cache()

    @model_validator(mode="after")
    def _convert_expected_to_null(self) -> Self:
        if self.expected is None:
            return self

        annotation = get_type_hints(self._processor_method.func, include_extras=True)
        if "expected" not in annotation:  # doesn't take an expected value
            self.__dict__["expected"] = None

        return self

    @model_validator(mode="after")
    def _convert_expected_to_type(self) -> Self:
        self._convert_expected_value(self._expected_type)
        return self

    @model_validator(mode="after")
    def _convert_expected_to_exact_field_type(self) -> Self:
        if is_typevar(self._actual_type) and is_typevar(self._expected_type):  # expected is same type as actual
            self._convert_expected_value(self._field_type)
        return self

    @model_validator(mode="after")
    def _convert_expected_to_generic_when_actual_is_sequence(self) -> Self:
        if is_typevar(self._expected_type) and self._field_type is str:
            self._convert_expected_value(self._field_type)
        elif (
                is_typevar(self._expected_type)
                and get_origin(self._actual_type) in {Sequence, UniqueSequence}
                and is_typevar(next(iter(get_args(self._actual_type))))
                and (expected_type := next(iter(get_args(self._field_type)), None)) is not None
        ):
            self._convert_expected_value(expected_type)

        return self

    @model_validator(mode="after")
    def _convert_expected_to_sequence_when_actual_is_generic(self) -> Self:
        if (
                  is_typevar(self._actual_type)
                  and get_origin(self._expected_type) in {set, Sequence, UniqueSequence}
                  and is_typevar(next(iter(get_args(self._expected_type)), None))
        ):
            expected_type = set[self._field_type]
            self._convert_expected_value(expected_type)

        return self

    @model_validator(mode="after")
    def _convert_expected_to_time_mapper(self) -> Self:
        if not isinstance(self.expected, str) or self._expected_type is str:
            return self

        with suppress(ValidationError):
            self.__dict__["expected"] = TimeMapper.model_validate(self.expected)

        return self

    def _convert_expected_value(self, expected_type: type) -> None:
        if self.expected is None or is_typevar(expected_type):
            return

        # prevent strings being split into list of characters
        if isinstance(self.expected, str) and get_origin(expected_type) in get_args(ItemCollection):
            self.expected = (self.expected,)

        value = self.expected
        with suppress(TypeError, ValueError, AttributeError):
            value = expected_type(value)

        try:
            value = TypeAdapter(expected_type).validate_python(value)
        except ValueError:
            return

        # need to explicitly compare types in this way as isinstance(False, int) is True
        if type(value) != type(self.expected) or value != self.expected:
            self.__dict__["expected"] = value

    def compare[IT: Any](self, item: IT, reference: IT | None = None) -> bool:
        """
        Compare a ``item`` to a ``reference`` or,
        if no ``reference`` is given, to this object's list of ``expected`` values

        :return: True if a match is found, False otherwise.
        :raise LocalProcessorError: If no reference given and no expected values set for this comparer.
        """
        self._validate_compare_args(reference=reference)

        actual_value = self._get_value_from_item(item)
        expected_value = self.expected
        if expected_value is None or self.reference_required:
            expected_value = self._get_value_from_item(reference)
        elif isinstance(expected_value, TimeMapper):  # apply map to current time for comparison
            expected_value = expected_value.apply(datetime.now())

        result = self._processor_method(actual_value, expected_value)
        return result

    @cached_property
    def _expected_args(self) -> list[str]:
        return inspect.getfullargspec(self._processor_method.func).args

    def _validate_compare_args(self, reference: Any | None = None) -> None:
        if reference is None and self.reference_required:
            raise MyTunesTypeError(f"A reference is required for this instance of {type(self).__name__}")

        if reference is None and "expected" in self._expected_args and not self.expected:
            raise MyTunesTypeError("No comparative item given and no expected values set")

    def _get_value_from_item(self, item: Any) -> Any:
        if self.field and isinstance(item, AttributeModel):
            value = getattr(item, self.field.lower())
        elif self.field and hasattr(item, self.field.lower()):
            value = getattr(item, self.field.lower())
        else:
            value = item

        if isinstance(value, HasName) and value.name:
            value = value.name

        return value

    @processormethod
    def _is[T](self, actual: T | None, expected: T | None) -> bool:
        if expected is None:
            return False
        return actual == expected

    @processormethod
    def _is_not[T](self, actual: T | None, expected: T | None) -> bool:
        return not self._is(actual=actual, expected=expected)

    @processormethod("greater_than", "in_the_last")
    def _is_after[T: Number](self, actual: T | None, expected: T | None) -> bool:
        if actual is None or expected is None:
            return False
        return actual > expected

    @processormethod("less_than", "not_in_the_last")
    def _is_before[T: Number](self, actual: T | None, expected: T | None) -> bool:
        if actual is None or expected is None:
            return False
        return actual < expected

    @processormethod
    def _is_in[T](self, actual: T, expected: set[T] | None) -> bool:
        return expected is not None and actual in expected

    @processormethod
    def _is_not_in[T](self, actual: T, expected: set[T] | None) -> bool:
        return not self._is_in(actual=actual, expected=expected)

    @processormethod
    def _in_range[T: Number](self, actual: T | None, expected: tuple[T, T] | None) -> bool:
        if actual is None or expected is None or expected[0] is None or expected[1] is None:
            return False
        return expected[0] <= actual <= expected[1]

    @processormethod
    def _not_in_range[T: Number](self, actual: T | None, expected: tuple[T, T] | None) -> bool:
        return not self._in_range(actual=actual, expected=expected)

    @processormethod
    def _is_not_null(self, actual: Any, *_) -> bool:
        return actual is not None or actual is True

    @processormethod
    def _is_null(self, actual: Any, *_) -> bool:
        return actual is None or actual is False

    @processormethod
    def _starts_with(self, actual: str | None, expected: str | None) -> bool:
        if actual is None or expected is None:
            return False
        return actual.startswith(expected)

    @processormethod
    def _ends_with(self, actual: Any | None, expected: str | None) -> bool:
        if actual is None or expected is None:
            return False
        return actual.endswith(expected)

    @processormethod
    def _contains[T](self, actual: Sequence[T] | None, expected: T | None) -> bool:
        if actual is None or expected is None:
            return False
        return expected in actual

    @processormethod
    def _does_not_contain[T](self, actual: Sequence[T] | None, expected: T | None) -> bool:
        return not self._contains(actual=actual, expected=expected)

    @processormethod
    def _matches_reg_ex(self, actual: str | None, expected: re.Pattern | None) -> bool:
        if actual is None or expected is None:
            return False
        return bool(re.search(expected, str(actual)))

    @processormethod
    def _matches_reg_ex_ignore_case(self, actual: str | None, expected: re.Pattern | None) -> bool:
        if actual is None or expected is None:
            return False
        return bool(re.search(expected, str(actual), flags=re.I))
