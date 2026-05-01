from collections.abc import Sequence, Iterable, Collection
from contextlib import suppress
from typing import Literal, Self, Annotated

from pydantic import Field, model_validator, PositiveInt, validate_call, \
    ValidationError, ConfigDict
from tabulate import tabulate
from termcolor import colored

from mytunes._types import TO_LIST
from mytunes.core.album import HasAlbum
from mytunes.core.artist import HasArtists
from mytunes.core.collection import CollectionModel
from mytunes.core.properties.date import HasReleaseDate
from mytunes.core.properties.length import HasLength
from mytunes.core.properties.name import HasName
from mytunes.core.properties.order import Position, HasTrackPosition
from mytunes.core.properties.uri import HasImmutableURI, HasMutableURI
from mytunes.exception import MyTunesTypeError, MyTunesValidationError
from .._base import BaseModel
from .._base.resource import ResourceModel
from .._utils import truncate_string

FIELDS = Literal[
    "Name", "Album", "Artist", "Released At", "Length", "URI", "Public URL"
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


class ModelFormatter[RT: ResourceModel](BaseModel):
    """A formatter for a BaseModel. This is used to format the model's data for output."""
    model_config = ConfigDict(frozen=True)

    fields: Sequence[FIELDS] = Field(
        description="The fields of the model to include in the formatted output.",
        min_length=1,
    )
    alignments: Annotated[Sequence[ALIGNMENTS], TO_LIST] | None = Field(
        description="The alignments of the fields in the formatted output. Must be the same length as `fields`.",
        default=None,
        min_length=1,
    )
    widths: Annotated[Sequence[PositiveInt | None], TO_LIST] | None = Field(
        description="The widths of the fields in the formatted output. Must be the same length as `fields`.",
        default=None,
        min_length=1,
    )
    truncate: Annotated[Sequence[bool], TO_LIST] | None = Field(
        description="Whether to truncate the fields in the formatted output. Must be the same length as `fields`.",
        default=None,
        min_length=1,
    )
    colours: Annotated[
        Sequence[COLOURS | tuple[int, int, int] | None],
        TO_LIST
    ] | None = Field(
        description="The colours to assign to each column. Must be the same length as `fields`.",
        default=None,
        min_length=1,
    )
    colour_attributes: Annotated[
        Sequence[Annotated[Sequence[COLOUR_ATTRIBUTES], TO_LIST] | None],
        TO_LIST
    ] | None = Field(
        description="The colour attributes to assign to each column. Must be the same length as `fields`.",
        default=None,
        min_length=1,
    )
    missing_value: str = Field(
        description="The value to use in the output when a field is missing.",
        default="",
    )

    table_format: str = Field(
        description="The format to use for the table.",
        default="orgtbl",
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
            return None
        if len(value) != 1 or len(self.fields) == 1:
            return None

        self.__dict__[name] = list(value) * len(self.fields)

    def _validate_lengths_match_fields(self, name: str) -> None:
        value = getattr(self, name)
        if value is None:
            return None

        if len(value) != len(self.fields):
            raise MyTunesValidationError(
                f"The number of {name} must match the number of fields: "
                f"{len(value)} {name} != {len(self.fields)} fields"
            )

        return None

    def format(self, item: RT | Iterable[RT], indices: bool | Sequence = False) -> str:
        """Format the given item."""
        match item:
            case ResourceModel():
                rows = [self._format_row(item)]
            case Iterable():
                rows = [self._format_row(i) for i in item]
            case _:
                raise MyTunesTypeError("Item must be a ResourceModel or a sequence of ResourceModels.")

        return tabulate(
            rows,
            headers=self.fields if self.header else (),
            colalign=self.alignments,
            maxcolwidths=self.widths,
            tablefmt=self.table_format,
            missingval=self.missing_value,
            showindex=indices if isinstance(indices, bool) else list(map(str, indices)),
            # WORKAROUND: needed to avoid parsing coloured number strings as int, which causes tabulate to
            #  throw ValueError when trying to cast these strings to int as the ANSI codes are still
            #  present in the string value when casting
            disable_numparse=True,
        )

    def _format_row(self, item: RT) -> tuple:
        row = []
        for position, field in enumerate(self.fields):
            getter = getattr(self, f"_get_{field.lower().replace(" ", "_")}")

            value = None
            with suppress(ValidationError):  # just use the default missing value if the getter fails
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

        if width is not None and should_truncate:
            value = truncate_string(str(value), width)
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
    def _get_artist(item: HasArtists) -> str | None:
        return str(item.artist) if item.artist is not None else None

    @staticmethod
    @validate_call
    def _get_album(item: HasAlbum) -> str | None:
        return str(item.album.name) if item.album is not None else None

    @staticmethod
    @validate_call
    def _get_length(item: HasLength) -> str | None:
        return str(item.length) if item.length is not None else None

    @staticmethod
    @validate_call
    def _get_released_at(item: HasReleaseDate) -> str | None:
        return str(item.released_at) if item.released_at is not None else None

    @staticmethod
    @validate_call
    def _get_uri(item: HasImmutableURI | HasMutableURI) -> str | None:
        return str(item.uri) if item.uri is not None else None

    @staticmethod
    @validate_call
    def _get_public_url(item: HasImmutableURI | HasMutableURI) -> str | None:
        return str(item.uri.public_url) if item.uri is not None else None


class CollectionFormatter[CT: CollectionModel](ModelFormatter[CT]):
    def format(self, collection: CT | Sequence, indices: bool | Sequence = False) -> str:
        items = []
        match collection:
            case CollectionModel() if collection.total:
                items.extend(collection.items)
            case Sequence() if all(isinstance(it, ResourceModel) for it in collection):
                items.extend(collection)
            case _:
                return super().format(collection, indices=indices)

        if indices is True:
            indices = self._get_indices_from_positions(items)
        return super().format(items, indices=indices)

    @staticmethod
    def _get_indices_from_positions(items: Collection[HasTrackPosition]) -> list[Position]:
        positions = [item.track for item in items if isinstance(item, HasTrackPosition) and item.track is not None]
        if not positions:
            total = len(items)
            return [Position(number=i, total=total, zero_fill=True) for i in range(1, total + 1)]

        total = max(
            max(i.number or 0 for i in positions),
            max(i.total or 0 for i in positions),
            len(items),
        )

        return [
            Position(
                number=i.number if i.number else i,
                total=i.total or total,
                zero_fill=True
            )
            for i in positions
        ]
