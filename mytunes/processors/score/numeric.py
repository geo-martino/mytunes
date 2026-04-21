from typing import Literal, final

from pydantic import Field, PositiveInt, PositiveFloat

from mytunes._types import Number
from mytunes.processors.clean.numeric import NumericCleaner, LengthCleaner, ReleaseYearCleaner, \
    TotalItemsCleaner
from mytunes.processors.score._base import Scorer


# noinspection PyAbstractClass
class NumericScorer[ST: str, CT: NumericCleaner](Scorer[ST, CT]):

    @staticmethod
    def _calculate_difference_score[T: Number](value: T, other: T | None, max_range: T = None) -> float:
        if not value or not other:
            return 0
        if max_range is None:
            max_range = other
        return max((max_range - abs(other - value)), 0) / max_range


# noinspection PyAbstractClass
class RangeScorer[ST: str, CT: NumericCleaner](NumericScorer[ST, CT]):
    range: PositiveInt | PositiveFloat | None = Field(
        description=(
            "The range within which the score will be calculated. "
            "Score=1 if the values are the same. "
            "Score=0 if the values are different by at least this range."
        ),
        default=None,
    )

    def _calculate_score(self, value: float, other: float | None) -> float:
        return self._calculate_difference_score(value, other, max_range=self.range)


@final
class LengthScorer(RangeScorer[Literal["length"], LengthCleaner]):
    """Score items by comparing lengths. Score=0 when either value is None."""
    __final__ = True


@final
class ReleaseYearScorer(RangeScorer[Literal["release_year"], ReleaseYearCleaner]):
    """Score items by comparing release years. Score=0 when either value is None."""
    __final__ = True

    range: PositiveInt = 10


@final
class TotalItemsScorer(NumericScorer[Literal["total_items"], TotalItemsCleaner]):
    """Score collections by comparing total items count. Score=0 when either value is None."""
    __final__ = True

    def _calculate_score(self, value: int, other: int | None) -> float:
        return self._calculate_difference_score(value, other)
