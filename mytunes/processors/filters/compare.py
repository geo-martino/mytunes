from collections.abc import Iterable, Mapping, Collection
from contextlib import suppress
from typing import Self, Any, final

from pydantic import Field, field_validator, field_serializer, validate_call, ValidationError, model_validator

from ..._models import ResourceModel
from mytunes.processors.compare import Comparer
from mytunes.processors.filters._base import Filter


@final
class ComparerFilter[IT: str | ResourceModel](Filter[IT]):
    """Filter based on a defined map of :py:class:`Comparer` objects mapped to additional ."""
    __final__ = True

    comparers: Mapping[Comparer, Self] = Field(
        description=(
            "Comparers to filter against. Mapped to additional filters where the first boolean indicates "
            "whether to AND (True) or OR (False) the comparer and sub-filter results."
        ),
        default_factory=dict,
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

        return data

    @field_validator("comparers", mode="before", check_fields=True)
    @classmethod
    def _comparer_to_mapping(
        cls, value: Comparer | Iterable[Comparer] | Mapping[str, Self]
    ) -> Mapping[str, tuple[bool, Self]]:
        if isinstance(value, Comparer):
            value = [value]
        if not isinstance(value, Mapping):
            value = {comparer: ComparerFilter() for comparer in value}

        return value

    @field_serializer("comparers", check_fields=True)
    def _flatten_comparers[T: Mapping[Comparer, tuple]](self, comparers: T) -> T | list[Comparer]:
        if all(not sub_filter.ready for sub_filter in comparers.values()):
            return list(self.comparers.keys())
        return comparers

    @property
    def ready(self) -> bool:
        return len(self.comparers) > 0

    @validate_call
    def check(self, item: IT, reference: IT | None = None, *_, **__) -> bool:
        # initial state determined by ready and match_all states
        matched = self.ready and self.match_all

        for comparer, sub_filter in self.comparers.items():
            cmp_match = comparer.compare(item=item, reference=reference)
            sub_match = sub_filter.check(item=item, reference=reference)

            combined_match = (cmp_match and sub_match) if sub_filter.combine_all else (cmp_match or sub_match)
            matched = (matched and combined_match) if self.match_all else (matched or combined_match)

        return matched

    def __eq__(self, item: Any):
        return isinstance(item, type(self)) and all((
            self.comparers == item.comparers,
            self.match_all == item.match_all,
            self.combine_all == item.combine_all,
        ))
