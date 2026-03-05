from typing import Literal, final

from pydantic import Field, PositiveInt, PositiveFloat

from musify.processors_new.match.clean.numeric import NumericCleaner, LengthCleaner, ReleaseYearCleaner
from musify.processors_new.match.score._base import Scorer


# noinspection PyAbstractClass
class NumericScorer[C: NumericCleaner](Scorer[C]):
    pass


# noinspection PyAbstractClass
class RangeScorer[C: NumericCleaner](NumericScorer[C]):
    range: PositiveInt | PositiveFloat = Field(
        description=(
            "The range within which the score will be calculated. "
            "Score=1 if the values are the same. "
            "Score=0 if the values are different by at least this range."
        ),
    )

    def _calculate_range_score(self, value: float, other: float | None) -> float:
        if not value or not other:
            return 0
        return max((self.range - abs(other - value)), 0) / self.range


@final
class LengthScorer(NumericScorer[LengthCleaner]):
    """Score items by comparing lengths. Score=0 when either value is None."""
    __final__ = True

    type: Literal["length"] = "length"
    cleaner: LengthCleaner = LengthCleaner()

    def _calculate_score(self, value: float, other: float | None) -> float:
        if not value or not other:
            return 0
        return max((other - abs(other - value)), 0) / other


@final
class ReleaseYearScorer(RangeScorer[ReleaseYearCleaner]):
    """Score items by comparing release years. Score=0 when either value is None."""
    __final__ = True

    type: Literal["release_year"] = "release_year"
    cleaner: ReleaseYearCleaner = ReleaseYearCleaner()
    range: PositiveInt = 10

    def _calculate_score(self, value: int, other: int | None) -> float:
        if not value or not other:
            return 0

        score = self._calculate_range_score(value, other)
        return score
