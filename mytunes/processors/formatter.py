from collections.abc import Sequence, Iterable, Collection
from contextlib import suppress
from typing import Literal, Self, Annotated

from pydantic import Field, model_validator, PositiveInt, validate_call, ValidationError, ConfigDict, InstanceOf
from rich import box
from rich.table import Table

from mytunes._types import TO_LIST, StrippedString
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
ALIGNMENTS = Literal["default", "left", "center", "right", "full"]


class ModelFormatter[RT: ResourceModel](BaseModel):
    """A formatter for a BaseModel. This is used to format the model's data for output."""
    model_config = ConfigDict(frozen=True)

    fields: Sequence[FIELDS] = Field(
        description="The fields of the model to include in the formatted output.",
        min_length=1,
    )
    alignments: Annotated[Sequence[ALIGNMENTS | None], TO_LIST] | None = Field(
        description="The alignments of the fields in the formatted output. Must be the same length as `fields`.",
        default=None,
        min_length=1,
    )
    widths: Annotated[Sequence[PositiveInt | None], TO_LIST] | None = Field(
        description="The widths of the fields in the formatted output. Must be the same length as `fields`.",
        default=None,
        min_length=1,
    )
    truncate: Annotated[Sequence[bool | None], TO_LIST] | None = Field(
        description="Whether to truncate the fields in the formatted output. Must be the same length as `fields`.",
        default=None,
        min_length=1,
    )
    styles: Annotated[Sequence[StrippedString | None], TO_LIST] | None = Field(
        description="The styles to assign to each column. Must be the same length as `fields`.",
        default=None,
        min_length=1,
    )
    missing_value: str | None = Field(
        description="The value to use in the output when a field is missing.",
        default="",
    )

    table_format: InstanceOf[box.Box] = Field(
        description="The format to use for the table.",
        default=box.ASCII,
        exclude=True,
    )
    header: bool = Field(
        description="Whether to include the header in the output.",
        default=False,
    )

    @model_validator(mode="after")
    def _validate_widths(self) -> Self:
        self._expand_for_all_fields("widths")
        self._validate_lengths_match_fields("widths")
        return self

    @model_validator(mode="after")
    def _validate_alignments(self) -> Self:
        self._expand_for_all_fields("alignments")
        self._validate_lengths_match_fields("alignments")
        return self

    @model_validator(mode="after")
    def _validate_truncate(self) -> Self:
        self._expand_for_all_fields("truncate")
        self._validate_lengths_match_fields("truncate")
        return self

    @model_validator(mode="after")
    def _validate_styles(self) -> Self:
        self._expand_for_all_fields("styles")
        self._validate_lengths_match_fields("styles")
        return self

    def _expand_for_all_fields(self, name: str) -> None:
        value = getattr(self, name)
        if value is None:
            value = [None]
        if len(value) != 1 or len(self.fields) == 1:
            return None

        self.__dict__[name] = list(value) * len(self.fields)
        return None

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

    def format(self, item: RT | Iterable[RT], indices: bool | Sequence = False) -> Table:
        """Format the given item."""
        match item:
            case ResourceModel():
                rows = [self._format_row(item)]
            case Iterable():
                rows = [self._format_row(i) for i in item]
            case _:
                raise MyTunesTypeError("Item must be a ResourceModel or a sequence of ResourceModels.")

        table = Table(show_header=self.header, box=self.table_format)
        if indices:
            table.add_column(no_wrap=True)
        columns = zip(self.fields, self.alignments, self.widths, self.styles, self.truncate, strict=True)
        for name, alignment, width, style, truncate in columns:
            table.add_column(
                name,
                justify=alignment if alignment else "default",
                width=width,
                style=style,
                no_wrap=truncate,
                overflow="ellipsis" if truncate else "fold",
            )

        if indices is True:
            rows = ((i, *row) for i, row in enumerate(rows, 1))
        elif isinstance(indices, Sequence):
            rows = ((str(i), *row) for i, row in zip(indices, rows))

        for row in rows:
            table.add_row(*row)

        return table

    def _format_row(self, item: RT) -> tuple:
        row = []
        for position, field in enumerate(self.fields):
            getter = getattr(self, f"_get_{field.lower().replace(" ", "_")}")

            value = None
            with suppress(ValidationError):  # just use the default missing value if the getter fails
                value = getter(item)

            row.append(value if value is not None else self.missing_value)

        return tuple(row)

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
    def format(self, collection: CT | Sequence, indices: bool | Sequence = False) -> Table:
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
