from collections.abc import Sequence
from typing import Annotated

from pydantic import Field

from mytunes._types import TO_TUPLE
from mytunes.exception import MyTunesValueError
from ..._models.properties.uri import HasURI
from ..._models.result import Result, LenLogFormatter


class CheckResult[T: HasURI](Result):
    """Stores the results of the searching process."""
    changed: Annotated[
        Sequence[T],
        TO_TUPLE,
        LenLogFormatter(
            width=6, alignment="right", colour="blue", colour_attributes=["bold"], condition=lambda x: x == 0
        ),
        LenLogFormatter(
            width=6, alignment="right", colour="green", colour_attributes=["bold"], condition=lambda x: x > 0
        ),
    ] = Field(
        description="The items that had their matches changed during the check.",
        default_factory=tuple
    )
    unchanged: Annotated[
        Sequence[T],
        TO_TUPLE,
        LenLogFormatter(
            width=6, alignment="right", colour="blue", colour_attributes=["bold"], condition=lambda x: x == 0
        ),
        LenLogFormatter(
            width=6, alignment="right", colour="green", colour_attributes=["bold"], condition=lambda x: x > 0
        ),
    ] = Field(
        description="The items that didn't have their matches changed during the check.",
        default_factory=tuple
    )
    unavailable: Annotated[
        Sequence[T],
        TO_TUPLE,
        LenLogFormatter(
            width=6, alignment="right", colour="green", colour_attributes=["bold"], condition=lambda x: x == 0
        ),
        LenLogFormatter(
            width=6, alignment="right", colour="yellow", colour_attributes=["bold"], condition=lambda x: x > 0
        ),
    ] = Field(
        description="The items that were marked as unavailable during the check.",
        default_factory=tuple
    )
    skipped: Annotated[
        Sequence[T],
        TO_TUPLE,
        LenLogFormatter(
            width=6, alignment="right", colour="green", colour_attributes=["bold"], condition=lambda x: x == 0
        ),
        LenLogFormatter(
            width=6, alignment="right", colour="blue", colour_attributes=["bold"], condition=lambda x: x > 0
        ),
    ] = Field(
        description="The items that were skipped during the check.",
        default_factory=tuple
    )

    def merge_results(self, other: CheckResult[T]) -> CheckResult[T]:
        """
        Merge another result into this one and return the merged result.
        The other result should only contain items that are in the skipped category as
        the other categories should contain items which do not reduce between operations.
        """
        skipped = list(self.skipped)

        for item in list(other.changed) + list(other.unavailable):
            if item not in skipped:
                raise MyTunesValueError("Can only merge with results which update the skipped items of this result")
            skipped.remove(item)

        for item in other.skipped:
            if item not in skipped:
                raise MyTunesValueError("Other result must contain all items in this result's skipped items")

        return CheckResult(
            changed=list(self.changed) + list(other.changed),
            unchanged=list(self.unchanged) + list(other.unchanged),
            unavailable=list(self.unavailable) + list(other.unavailable),
            skipped=list(self.skipped) + list(other.skipped),
        )
