from collections.abc import Iterable, Mapping, Collection, Sequence
from contextlib import suppress
from typing import Self, Any, final, Annotated, Literal

from mytunes._types import TO_TUPLE
from mytunes.exception import MyTunesValidationError
from pydantic import Field, field_validator, field_serializer, validate_call, ValidationError, model_validator

from ..._base.resource import ResourceModel
from mytunes.processors.compare import Comparer
from mytunes.processors.filters._base import Filter


@final
class ComparerFilter[IT: str | ResourceModel](Filter[Literal["compare", "comparer"], IT]):
    """Filter based on a defined map of :py:class:`Comparer` objects mapped to additional ."""
    __final__ = True

    comparers: Annotated[Sequence[Comparer], TO_TUPLE] = Field(
        description="Comparers to filter against.",
        default_factory=tuple,
    )
    nested: Annotated[Sequence[Self | None], TO_TUPLE] | None = Field(
        description=(
            "Additional filters to apply in conjunction with comparers. "
            "Must match the comparers 1-to-1."
        ),
        default=None,
        validation_alias="filters",
    )
    match_all: bool = Field(
        description="When true, all comparers must match, otherwise any can match",
        default=True,
    )
    combine_all: bool | None = Field(
        description=(
            "Whether to combine the check with a parent filter. "
            "This is only used when this filter is a child of a parent comparer filter."
        ),
        default=None,
    )

    @model_validator(mode="before")
    @classmethod
    def _from_comparer[T](cls, data: T | Mapping[str, Any] | Collection[Mapping[str, Any]]) -> T | Mapping[Comparer, Self]:
        match data:
            case Mapping() if data:
                with suppress(ValidationError):
                    return dict(comparers=Comparer.model_validate(data))
            case Collection() if data and all(isinstance(value, Mapping) for value in data):
                return dict(comparers=[Comparer.model_validate(value) for value in data])

        data[cls.__discriminator_field__] = "compare"
        return data

    @model_validator(mode="after")
    def _validate_lengths_match(self) -> Self:
        if self.nested is None:
            return self

        if len(self.comparers) != len(self.nested):
            raise MyTunesValidationError(
                f"The number of comparers must match the number of nested filters when provided: "
                f"{len(self.comparers)} != {len(self.nested)}"
            )

    @property
    def ready(self) -> bool:
        return len(self.comparers) > 0

    @validate_call
    def check(self, item: IT, reference: IT | None = None) -> bool:
        # initial state determined by ready and match_all states
        matched = self.ready and self.match_all
        nested = self.nested or [None] * len(self.comparers)

        for comparer, sub_filter in zip(self.comparers, nested, strict=True):
            match = comparer.compare(item=item, reference=reference)
            if sub_filter is not None:
                sub_match = sub_filter.check(item=item, reference=reference) if sub_filter is not None else None
                match = (match and sub_match) if sub_filter.combine_all else (match or sub_match)

            matched = (matched and match) if self.match_all else (matched or match)

        return matched

    def __eq__(self, item: Any):
        return isinstance(item, type(self)) and all((
            self.comparers == item.comparers,
            self.match_all == item.match_all,
            self.combine_all == item.combine_all,
        ))
