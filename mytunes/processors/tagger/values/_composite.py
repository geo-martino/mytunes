from abc import abstractmethod
from collections.abc import Sequence
from string import Formatter
from typing import final, Self, Literal, Annotated

from pydantic import Field, model_validator, ValidationError, validate_call, BeforeValidator

from mytunes._types import StrippedString
from mytunes.exception import MyTunesValueError, MyTunesValidationError
from mytunes.processors._types import _ATTRIBUTE_FIELD_MAP
from mytunes.processors.tagger.values._fields import FieldValue, from_field_names
from ._base import Value
from ...._base.attribute import AttributeModel


# noinspection PyAbstractClass
class CompositeValue[OT: str, IT: AttributeModel](Value[OT, IT, str]):
    @abstractmethod
    def get(self, item: IT) -> str:
        """Get the combined value from the given item's tags."""
        raise NotImplementedError


@final
class JoinValue[IT: AttributeModel](CompositeValue[Literal["join"], IT]):
    """Formats a tag value according to a set of tag values to get and join with some separator."""
    __final__ = True

    fields: Annotated[Sequence[FieldValue.annotation], BeforeValidator(from_field_names)] = Field(
        description="The fields to use to get the final value.",
        default_factory=tuple,
    )
    separator: str = Field(
        description="The separator to use to join the tag values.",
        default="",
    )

    @validate_call
    def get(self, item: IT) -> str:
        field_values = {field.field: field.get(item) for field in self.fields}
        if invalid_fields := [name for name, value in field_values.items() if value is None]:
            raise MyTunesValueError(f"Some tag values could not be extracted: {", ".join(invalid_fields)}")

        return self.separator.join(field_values.values())


@final
class TemplateValue[IT: AttributeModel](CompositeValue[Literal["template"], IT]):
    """Formats a tag value according to a template of tag values to get."""
    __final__ = True

    template: StrippedString = Field(
        description="The template of the tag value.",
    )
    fields: Sequence[Value.annotation] = Field(
        description="The fields to use to format the template.",
        default_factory=tuple,
    )

    @model_validator(mode="after")
    def _extend_fields_with_template_fields(self) -> Self:
        field_names = set(name for _, name, _, _ in Formatter().parse(self.template) if name is not None)
        fields = list(self.fields)
        unrecognised_fields: list[str] = []

        for name in field_names:
            if not any(getter.field == name for getter in fields):
                try:
                    field = FieldValue.model_validate(dict(field=name))
                    fields.append(field)
                except ValidationError:
                    unrecognised_fields.append(name)

        if unrecognised_fields:
            errors = ", ".join(unrecognised_fields)
            expected = ", ".join(_ATTRIBUTE_FIELD_MAP)
            message = (
                f"Unrecognised fields in template: {errors}. If this is meant to be a custom field, "
                "consider adding its configuration to the template under 'fields'.\n"
                f"Supported fields: {expected}"
            )
            raise MyTunesValidationError(message)

        if fields != self.fields:
            self.__dict__["fields"] = fields

        return self

    @validate_call
    def get(self, item: IT) -> str:
        """Format the template from the fields of the given item."""
        field_values = {field.field: field.get(item) for field in self.fields}
        if invalid_fields := [name for name, value in field_values.items() if value is None]:
            raise MyTunesValueError(f"Some tag values could not be extracted: {", ".join(invalid_fields)}")

        return self.template.format_map(field_values)
