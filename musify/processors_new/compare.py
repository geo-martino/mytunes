"""
Processor making comparisons between objects and data types.
"""
import inspect
import re
import typing
from collections.abc import Sequence
from datetime import datetime
from types import NoneType
from typing import Any, Literal, Self

from pydantic import Field, field_validator, TypeAdapter, model_validator, \
    ModelWrapValidatorHandler
from pydantic.alias_generators import to_snake
from typing_inspection.introspection import is_union_origin
from typing_inspection.typing_objects import is_typevar

from musify._types import LowerSnakeCase
from musify.local.item.track import LocalTrack
from musify.models import MusifyResource
from musify.models.item.album import HasAlbum
from musify.models.properties.audio import IsAudioFile
from musify.models.properties.date import HasAddedDate, HasPlayedDate
from musify.models.properties.file import IsFile
from musify.models.properties.length import HasLength
from musify.models.properties.name import HasName
from musify.models.properties.order import HasTrackPosition, HasDiscPosition
from musify.models.properties.rating import HasRating
from musify.models.properties.uri import HasURI
from musify.processors_new._base import DynamicProcessor, dynamicprocessormethod
from musify.processors_new.exception import ComparerError
from musify.processors_new.time import TimeMapper

COMPARISON_FIELDS = frozenset({
    *LocalTrack.__tag_fields__,
    *IsFile.__tag_fields__,
    *IsAudioFile.__tag_fields__,
    *HasAddedDate.__tag_fields__,
    *HasPlayedDate.__tag_fields__,
    *HasLength.__tag_fields__,
    *HasName.__tag_fields__,
    *HasTrackPosition.__tag_fields__,
    *HasDiscPosition.__tag_fields__,
    *HasRating.__tag_fields__,
    *HasURI.__tag_fields__,
    *HasAlbum.__tag_fields__,
})


class Comparer(DynamicProcessor):
    """
    Compares an item or object with another item, object or a given set of expected values to find a match.

    The expected value given will be cast to the appropriate type based on the field being compared
    according to the type hints of the selected field.
    Attempts will be made to convert the expected value to the appropriate type based on Pydantic
    field type conversion rules.
    """
    condition: LowerSnakeCase = Field(
        description="The condition to match on.",
    )
    expected: Any = Field(
        description="Expected value/s to match on.",
        default=None,
    )
    field: Literal[*COMPARISON_FIELDS] | None = Field(
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
    def _processor_name(self) -> str:
        return self.condition

    @field_validator("condition", mode="before", check_fields=True)
    @staticmethod
    def _clean_processor_name(name: str) -> str:
        return to_snake(name).replace(" ", "_").strip("_")

    @field_validator("expected", mode="before", check_fields=True)
    @staticmethod
    def _convert_expected_to_time_mapper(expected: Any) -> Any:
        if not isinstance(expected, str):
            return expected

        try:
            return TimeMapper.model_validate(expected)
        except ValueError:
            return expected

    @property
    def _field_type(self) -> type:
        if self.field is None:
            field_type = NoneType
        elif (field := LocalTrack.__pydantic_fields__.get(self.field)) is not None:  # field is a model field
            field_type = field.annotation
        else:  # field is a property
            field = getattr(LocalTrack, self.field).fget
            field_type = typing.get_type_hints(field, include_extras=True)["return"]
        return self._extract_type_from_annotation(field_type)

    @property
    def _actual_type(self) -> type:
        annotation = typing.get_type_hints(self._processor_method.func, include_extras=True)["actual"]
        return self._extract_type_from_annotation(annotation)

    @property
    def _expected_type(self) -> type:
        annotation = typing.get_type_hints(self._processor_method.func, include_extras=True)
        if "expected" not in annotation:  # doesn't take an expected value
            return NoneType

        return self._extract_type_from_annotation(annotation["expected"])

    def _extract_type_from_annotation(self, annotation) -> type:
        origin = typing.get_origin(annotation)
        if is_union_origin(origin):
            types = typing.get_args(annotation)
            types = [t for t in types if t is not NoneType]
            annotation_type = types[0] if len(types) == 1 else typing.Union[tuple(types)]
        else:
            annotation_type = annotation

        return annotation_type

    @model_validator(mode="wrap")
    @classmethod
    def _convert_expected_to_null(
            cls, data: Any, handler: ModelWrapValidatorHandler[Self]
    ) -> Self:
        model: Self = handler(data)
        if model.expected is None:
            return model

        annotation = typing.get_type_hints(model._processor_method.func, include_extras=True)
        if "expected" not in annotation:  # doesn't take an expected value
            model.expected = None

        return model

    @model_validator(mode="wrap")
    @classmethod
    def _convert_expected_to_type(
            cls, data: Any, handler: ModelWrapValidatorHandler[Self]
    ) -> Self:
        model: Self = handler(data)
        model._convert_expected_value(model._expected_type)

        return model

    @model_validator(mode="wrap")
    @classmethod
    def _convert_expected_to_exact_field_type(
            cls, data: Any, handler: ModelWrapValidatorHandler[Self]
    ) -> Self:
        model: Self = handler(data)
        if is_typevar(model._actual_type) and is_typevar(model._expected_type):  # expected is same type as actual
            model._convert_expected_value(model._field_type)

        return model

    @model_validator(mode="wrap")
    @classmethod
    def _convert_expected_to_generic_when_actual_is_sequence(
            cls, data: Any, handler: ModelWrapValidatorHandler[Self]
    ) -> Self:
        model: Self = handler(data)
        if is_typevar(model._expected_type) and model._field_type is str:
            model._convert_expected_value(model._field_type)
        elif (
                is_typevar(model._expected_type)
                and typing.get_origin(model._actual_type) is Sequence
                and is_typevar(next(iter(typing.get_args(model._actual_type))))
                and (expected_type := next(iter(typing.get_args(model._field_type)), None)) is not None
        ):
            model._convert_expected_value(expected_type)

        return model

    @model_validator(mode="wrap")
    @classmethod
    def _convert_expected_to_sequence_when_actual_is_generic(
            cls, data: Any, handler: ModelWrapValidatorHandler[Self]
    ) -> Self:
        model: Self = handler(data)
        if (
                  is_typevar(model._actual_type)
                  and typing.get_origin(model._expected_type) in (Sequence, set)
                  and is_typevar(next(iter(typing.get_args(model._expected_type)), None))
        ):
            expected_type = set[model._field_type]
            model._convert_expected_value(expected_type)

        return model

    def _convert_expected_value(self, expected_type: type) -> None:
        if self.expected is None or is_typevar(expected_type):
            return

        try:
            value = expected_type(self.expected)
        except (TypeError, ValueError):
            value = self.expected

        try:
            value = TypeAdapter(expected_type).validate_python(value)
        except ValueError:
            return

        # need to explicitly compare types in this way as isinstance(False, int) is True
        if type(value) != type(self.expected) or value != self.expected:
            self.expected = value

    def __call__(self, *args, **kwargs) -> bool:
        return self.compare(*args, **kwargs)

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

        return super().__call__(actual_value, expected_value)

    def _validate_compare_args(self, reference: Any | None = None) -> None:
        if reference is None and self.reference_required:
            raise ComparerError("A reference is required for this instance of Comparer")
        signature = inspect.getfullargspec(self._processor_method.func)
        if reference is None and "expected" in signature.args and not self.expected:
            raise ComparerError("No comparative item given and no expected values set")

    def _get_value_from_item(self, item: Any) -> Any:
        if self.field and isinstance(item, MusifyResource):
            value = getattr(item, self.field.lower())
        else:
            value = item

        if isinstance(value, HasName):
            value = value.name

        return value

    @dynamicprocessormethod
    def _is[T](self, actual: T | None, expected: T | None) -> bool:
        if expected is None:
            return False
        return actual == expected

    @dynamicprocessormethod
    def _is_not[T](self, actual: T | None, expected: T | None) -> bool:
        return not self._is(actual=actual, expected=expected)

    @dynamicprocessormethod("greater_than", "in_the_last")
    def _is_after[T: int | float](self, actual: T | None, expected: T | None) -> bool:
        if actual is None or expected is None:
            return False
        return actual > expected

    @dynamicprocessormethod("less_than", "not_in_the_last")
    def _is_before[T: int | float](self, actual: T | None, expected: T | None) -> bool:
        if actual is None or expected is None:
            return False
        return actual < expected

    @dynamicprocessormethod
    def _is_in[T](self, actual: T, expected: set[T] | None) -> bool:
        return expected is not None and actual in expected

    @dynamicprocessormethod
    def _is_not_in[T](self, actual: T, expected: set[T] | None) -> bool:
        return not self._is_in(actual=actual, expected=expected)

    @dynamicprocessormethod
    def _in_range[T: int | float](self, actual: T | None, expected: tuple[T, T] | None) -> bool:
        if actual is None or expected is None or expected[0] is None or expected[1] is None:
            return False
        return expected[0] <= actual <= expected[1]

    @dynamicprocessormethod
    def _not_in_range[T: int | float](self, actual: T | None, expected: tuple[T, T] | None) -> bool:
        return not self._in_range(actual=actual, expected=expected)

    @dynamicprocessormethod
    def _is_not_null(self, actual: Any, *_) -> bool:
        return actual is not None or actual is True

    @dynamicprocessormethod
    def _is_null(self, actual: Any, *_) -> bool:
        return actual is None or actual is False

    @dynamicprocessormethod
    def _starts_with(self, actual: str | None, expected: str | None) -> bool:
        if actual is None or expected is None:
            return False
        return actual.startswith(expected)

    @dynamicprocessormethod
    def _ends_with(self, actual: Any | None, expected: str | None) -> bool:
        if actual is None or expected is None:
            return False
        return actual.endswith(expected)

    @dynamicprocessormethod
    def _contains[T](self, actual: Sequence[T] | None, expected: T | None) -> bool:
        if actual is None or expected is None:
            return False
        return expected in actual

    @dynamicprocessormethod
    def _does_not_contain[T](self, actual: Sequence[T] | None, expected: T | None) -> bool:
        return not self._contains(actual=actual, expected=expected)

    @dynamicprocessormethod
    def _matches_reg_ex(self, actual: str | None, expected: re.Pattern | None) -> bool:
        if actual is None or expected is None:
            return False
        return bool(re.search(expected, actual))

    @dynamicprocessormethod
    def _matches_reg_ex_ignore_case(self, actual: str | None, expected: re.Pattern | None) -> bool:
        if actual is None or expected is None or expected[0] is None:
            return False
        return bool(re.search(expected, actual, flags=re.I))

    def __hash__(self):
        match self.expected:
            case None:
                expected = ""
            case set():
                expected = tuple(self.expected)
            case _:
                expected = self.expected

        return hash((
            self.condition, expected, self.field or "", self.reference_required
        ))

    def __eq__(self, item: Any):
        return isinstance(item, self.__class__) and all((
            self.condition == item.condition,
            self.expected == item.expected,
            self.field == item.field,
            self.reference_required == item.reference_required,
        ))
