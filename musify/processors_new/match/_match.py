from collections.abc import Sequence, Iterable
from copy import copy
from typing import Any

from pydantic import conlist, Field

from musify.models import AttributeModel
from musify.models.item.track import HasTracks, Track
from musify.models.properties.logger import HasLogger
from musify.models.properties.name import HasName
from musify.processors_new import Processor
from musify.processors_new.match.score import Scorer


class Matcher(Processor, HasLogger):
    """
    Matches items based on their attributes and the scorers provided.
    Scores will always be between 0 and 1, where 0 means no similarity and 1 means identical.
    """
    scorers: conlist(Scorer.annotation, min_length=1) = Field(
        description="The scorers to use for scoring the similarity between items.",
    )
    min_score: float = Field(
        description=(
            "The minimum score required to match items. "
            "Only returns the result as a match if the score is above this value.")
        ,
        default=0,
        ge=0,
        le=1,
    )
    max_score: float = Field(
        description=(
            "The maximum score required to match items. "
            "Scoring will always stop once this score has been reached. "
            "Additionally, any required scorers must score above this value individually for a match to be returned."
        ),
        default=1,
        gt=0,
        le=1,
    )
    score_items_in_collections: bool = Field(
        description=(
            "Whether to score items in collections. If False, only the collection itself will be scored. "
            "If True, the items in the collection will also be scored and contribute to the overall score."
        ),
        default=False,
    )

    def get_scorers_for_item(self, item: Any) -> list[Scorer]:
        """Get the scorers that can score the given item."""
        return [scorer for scorer in self.scorers if scorer.can_score(item)]

    def match[T: AttributeModel | HasName](self, item: T, others: Iterable[T]) -> T | None:
        """Matches the given item to the most similar other item."""
        best_match = None
        best_score = 0

        for other in others:
            score = self.score(item, other)
            if score > best_score:
                best_match = other
                best_score = score

            if score >= self.max_score:  # break early if a good enough match is found
                break

        if best_score < self.min_score:
            self.logger.debug(
                f"No match found for item {item.name} with score above the minimum score threshold. Returning None."
            )
            return None

        self.logger.debug(f"Matching item {item.name} with score {best_score}.")
        return best_match

    def score[T: AttributeModel | HasName](self, item: T, other: T) -> float:
        """Scores the similarity between the given items."""
        scorers = self.get_scorers_for_item(item)
        if not scorers:
            self.logger.warning(f"No scorers found for item {item.name}. Returning score of 0.")
            return 0

        scores = []
        weight = sum(scorer.weight for scorer in scorers)

        # apply required scorers first to allow for early stopping if they fail
        for scorer in filter(lambda x: x.required, scorers):
            score = scorer.score(item, other)
            if score < self.max_score:
                self.logger.debug(
                    f"Required scorer {scorer.type} scored {score} which is below the max score threshold. Stopping."
                )
                return 0

            scores.append(score)

        scores.extend(scorer.score(item, other) for scorer in filter(lambda x: not x.required, scorers))

        if self.score_items_in_collections:
            if isinstance(item, HasTracks) and isinstance(other, HasTracks):
                scores.extend(self._score_items(item.tracks, other.tracks))
                weight += len(item.tracks)

        return sum(scores) / weight

    def _score_items[T: Track](self, items: Sequence[T], others: Sequence[T]) -> list[float]:
        scores = []
        others = list(copy(others))  # safely mutable

        for item in items:
            score = 0

            for i, other in enumerate(others):
                score = self.score(item, other)

                if score >= self.max_score:  # break early if a good enough match is found
                    others.pop(i)  # remove the matched track to prevent it from being matched again
                    break

            scores.append(score)

        return scores
