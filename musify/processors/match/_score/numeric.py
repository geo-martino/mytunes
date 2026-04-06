from typing import Literal, final

from pydantic import Field, PositiveInt, PositiveFloat

from musify._types import Number
from musify.processors.clean.numeric import NumericCleaner, LengthCleaner, ReleaseYearCleaner, \
    TotalItemsCleaner
from musify.processors.match._score._base import Scorer


# noinspection PyAbstractClass
class NumericScorer[CT: NumericCleaner](Scorer[CT]):

    @staticmethod
    def _calculate_difference_score[T: Number](value: T, other: T | None, max_range: T = None) -> float:
        if not value or not other:
            return 0
        if max_range is None:
            max_range = other
        return max((max_range - abs(other - value)), 0) / max_range


# noinspection PyAbstractClass
class RangeScorer[CT: NumericCleaner](NumericScorer[CT]):
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
class LengthScorer(RangeScorer[LengthCleaner]):
    """Score items by comparing lengths. Score=0 when either value is None."""
    __final__ = True

    type: Literal["length"] = "length"
    cleaner: LengthCleaner = LengthCleaner()


@final
class ReleaseYearScorer(RangeScorer[ReleaseYearCleaner]):
    """Score items by comparing release years. Score=0 when either value is None."""
    __final__ = True

    type: Literal["release_year"] = "release_year"
    cleaner: ReleaseYearCleaner = ReleaseYearCleaner()
    range: PositiveInt = 10


@final
class TotalItemsScorer(NumericScorer[NumericCleaner]):
    """Score collections by comparing total items count. Score=0 when either value is None."""
    __final__ = True

    type: Literal["total_items"] = "total_items"
    cleaner: TotalItemsCleaner = TotalItemsCleaner()

    def _calculate_score(self, value: int, other: int | None) -> float:
        return self._calculate_difference_score(value, other)
