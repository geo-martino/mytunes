import contextlib
import textwrap
from collections.abc import Sequence, Iterable
from typing import Literal, Self, Annotated

from pydantic import Field, model_validator, PositiveInt, BeforeValidator, validate_call, \
    ValidationError
from tabulate import tabulate
from termcolor import colored

from musify._types import to_list
from musify.exception import MusifyValueError
from musify.models import BaseModel, BaseResource
from musify.models.collection import CollectionModel
from musify.models.properties.length import HasLength
from musify.models.properties.name import HasName
from musify.models.properties.order import Position, HasTrackPosition
from musify.models.properties.uri import HasURI

FIELDS = Literal[
    "Name", "Length", "URI", "Public URL"
]
ALIGNMENTS = Literal["left", "right", "center", "decimal"]
COLOURS = Literal[
    "black", "red", "green", "yellow", "blue", "magenta", "cyan", "white",
    "light_grey", "dark_grey", "light_red", "light_green", "light_yellow", "light_blue",
    "light_magenta", "light_cyan"
]
COLOUR_ATTRIBUTES = Literal[
    "bold", "dark", "italic", "underline", "blink", "reverse", "concealed", "strike"
]


class ModelFormatter[RT: BaseResource](BaseModel):
    """A formatter for a BaseModel. This is used to format the model's data for output."""

    fields: Sequence[FIELDS] = Field(
        description="The fields of the model to include in the formatted output.",
        min_length=1,
    )
    alignments: Annotated[Sequence[ALIGNMENTS], BeforeValidator(to_list)] | None = Field(
        description="The alignments of the fields in the formatted output. Must be the same length as `fields`.",
        default=None,
        min_length=1,
    )
    widths: Annotated[Sequence[PositiveInt], BeforeValidator(to_list)] | None = Field(
        description="The widths of the fields in the formatted output. Must be the same length as `fields`.",
        default=None,
        min_length=1,
    )
    truncate: Annotated[Sequence[bool], BeforeValidator(to_list)] | None = Field(
        description="Whether to truncate the fields in the formatted output. Must be the same length as `fields`.",
        default=None,
        min_length=1,
    )
    colours: Annotated[
        Sequence[COLOURS | tuple[int, int, int] | None],
        BeforeValidator(to_list)
    ] | None = Field(
        description="The colours to assign to each column. Must be the same length as `fields`.",
        default=None,
        min_length=1,
    )
    colour_attributes: Annotated[
        Sequence[Annotated[Sequence[COLOUR_ATTRIBUTES], BeforeValidator(to_list)] | None],
        BeforeValidator(to_list)
    ] | None = Field(
        description="The colour attributes to assign to each column. Must be the same length as `fields`.",
        default=None,
        min_length=1,
    )
    missing_value: str = Field(
        description="The value to use in the output when a field is missing.",
        default="",
    )
    header: bool = Field(
        description="Whether to include the header in the output.",
        default=False,
    )

    @model_validator(mode="after")
    def _validate_widths(self) -> Self:
        self._expand_single_item_to_all_fields("widths")
        self._validate_lengths_match_fields("widths")
        return self

    @model_validator(mode="after")
    def _validate_alignments(self) -> Self:
        self._expand_single_item_to_all_fields("alignments")
        self._validate_lengths_match_fields("alignments")
        return self

    @model_validator(mode="after")
    def _validate_truncate(self) -> Self:
        self._expand_single_item_to_all_fields("truncate")
        self._validate_lengths_match_fields("truncate")
        return self

    @model_validator(mode="after")
    def _validate_truncate(self) -> Self:
        self._expand_single_item_to_all_fields("truncate")
        self._validate_lengths_match_fields("truncate")
        return self

    @model_validator(mode="after")
    def _validate_colours(self) -> Self:
        self._expand_single_item_to_all_fields("colours")
        self._validate_lengths_match_fields("colours")
        return self

    @model_validator(mode="after")
    def _validate_colour_attributes(self) -> Self:
        self._expand_single_item_to_all_fields("colour_attributes")
        self._validate_lengths_match_fields("colour_attributes")
        return self

    def _expand_single_item_to_all_fields(self, name: str) -> None:
        value = getattr(self, name)
        if value is None:
            return
        if len(value) != 1 or len(self.fields) == 1:
            return

        setattr(self, name, list(value) * len(self.fields))

    def _validate_lengths_match_fields(self, name: str) -> None:
        value = getattr(self, name)
        if value is None:
            return

        if len(value) != len(self.fields):
            raise MusifyValueError(
                f"The number of {name} must match the number of fields. "
                f"{len(value)} {name} != {len(self.fields)} fields."
            )

    def format(self, item: RT | Iterable[RT], indices: bool | Sequence = False) -> str:
        """Format the given item."""
        match item:
            case BaseResource():
                rows = [self._format_row(item)]
            case Iterable():
                rows = [self._format_row(i) for i in item]
            case _:
                raise MusifyValueError("Item must be a BaseResource or a sequence of BaseResources.")

        return tabulate(
            rows,
            headers=self.fields if self.header else (),
            colalign=self.alignments,
            maxcolwidths=self.widths,
            tablefmt="orgtbl",
            missingval=self.missing_value,
            showindex=indices if isinstance(indices, bool) else list(map(str, indices)),
        )

    def _format_row(self, item: RT) -> tuple:
        row = []
        for position, field in enumerate(self.fields):
            getter = getattr(self, f"_get_{field.lower().replace(" ", "_")}")

            value = None
            with contextlib.suppress(ValidationError):  # just use the default missing value if the getter fails
                value = getter(item)

            value = self._truncate_value_if_needed(value, position)
            value = self._colour_value_if_needed(value, position)
            if value is None:
                value = self.missing_value if self.missing_value else ""

            row.append(value)

        return tuple(row)

    def _truncate_value_if_needed[T](self, value: T, position: int) -> T | str:
        if self.widths is None or self.truncate is None:
            return value

        width = self.widths[position]
        should_truncate = self.truncate[position]

        if should_truncate:
            value = textwrap.shorten(str(value), width, placeholder="...")
        return value

    def _colour_value_if_needed[T](self, value: T, position: int) -> T | str:
        if value is None or (self.colours is None and self.colour_attributes is None):
            return value

        colour = self.colours[position] if self.colours else None
        attributes = self.colour_attributes[position] if self.colour_attributes else None

        value = colored(str(value), color=colour, attrs=attributes)
        return value

    @staticmethod
    @validate_call
    def _get_name(item: HasName) -> str | None:
        return item.name

    @staticmethod
    @validate_call
    def _get_length(item: HasLength) -> str | None:
        return str(item.length) if item.length is not None else None

    @staticmethod
    @validate_call
    def _get_uri(item: HasURI) -> str | None:
        return str(item.uri) if item.uri is not None else None

    @staticmethod
    @validate_call
    def _get_public_url(item: HasURI) -> str | None:
        return str(item.uri.public_url) if item.uri is not None else None


class CollectionFormatter[CT: CollectionModel](ModelFormatter[CT]):
    def format(self, collection: CT, indices: bool | Sequence = False) -> str:
        # noinspection PyTypeChecker
        match indices:
            case True if all(isinstance(item, HasTrackPosition) for item in collection.iter_items):
                total = collection.count
                # noinspection PyTypeChecker
                indices = [
                    Position(
                        number=item.track.number if item.track and item.track.number else i,
                        total=total,
                        zero_fill=True
                    )
                    for i, item in enumerate(collection.iter_items, 1)
                ]
            case True:
                # noinspection PyTypeChecker
                total: int = collection.count
                indices = [Position(number=i, total=total, zero_fill=True) for i in range(1, total + 1)]
            case _:
                indices = False

        # noinspection PyTypeChecker
        return super().format(collection.iter_items, indices=indices)
