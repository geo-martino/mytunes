from typing import Any

from pydantic import conlist, Field

from musify.processors_new import Processor
from musify.processors_new.match.score import Scorer, ScorerType


class Matcher(Processor):
    scorers: conlist(ScorerType, min_length=1) = Field(
        description="The scorers to use for scoring the similarity between items.",
    )
    min_score: float = Field(
        description=(
            "The minimum score required to match items. "
            "Only returns the result as a match if the score is above this value.")
        ,
        default=0,
        ge=0,
        lt=1,
    )
    max_score: float = Field(
        description=(
            "The maximum score required to match items. "
            "Scoring will stop once this score has been reached."
        ),
        default=1,
        gt=0,
        le=1,

    )

    def get_scorers_for_item(self, item: Any) -> list[Scorer]:
        """Get the scorers that can score the given item."""
        return [scorer for scorer in self.scorers if scorer.can_score(item)]
