from collections.abc import Sequence, Collection
from copy import copy
from typing import Any

from pydantic import conlist, Field

from musify.models import AttributeModel
from musify.models.collection import CollectionModel
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

    def match[T: AttributeModel | HasName](self, item: T, others: Collection[T]) -> T | None:
        """Matches the given item to the most similar other item."""
        if not others:
            message = "No items to match against"
            log = self._format_item_message(method="SKIP", item=item, messages=message, pad="<")
            self.logger.debug(log)
            return None

        best_match = None
        best_score = 0

        scorers = self.get_scorers_for_item(item)
        if not scorers:
            message = "No configured scorers can score this item"
            log = self._format_item_message(method="SKIP", item=item, messages=message, pad="<")
            self.logger.debug(log)
            return None

        self._log_scorers(scorers, item=item, others=others)

        for other in others:
            score = self.score(scorers, item=item, other=other)
            if score > best_score:
                best_match = other
                best_score = score

            if score >= self.max_score:  # break early if a good enough match is found
                message = [self._get_item_log_value(other), "MAX SCORE REACHED"]
                log = self._format_item_message(method="BREAK", item=item, messages=message, pad=" ")
                self.logger.debug(log)
                break

        if best_score < self.min_score:
            message = "MIN SCORE NOT REACHED"
            log = self._format_item_message(method="FAILED", item=item, messages=message, pad="<")
            self.logger.debug(log)
            return None

        message = [self._get_item_log_value(best_match), f"{"SCORE":>10}={best_score}"]
        log = self._format_item_message(method="MATCHED", item=item, messages=message, pad="<")
        self.logger.debug(log)

        return best_match

    def _log_scorers(self, scorers: list[Scorer], item: Any, others: Collection) -> None:
        """Log the scorers being used for a given item and other item."""
        required = [scorer for scorer in scorers if scorer.required]
        optional = [scorer for scorer in scorers if not scorer.required]
        messages = [
            f"ITEMS: {len(others)}",
            f"REQUIRED: {", ".join(scorer.type for scorer in required)}" if required else "No required scorers",
            f"OPTIONAL: {", ".join(scorer.type for scorer in optional)}" if required else "No optional scorers",
        ]
        log = self._format_item_message(method="START", item=item, messages=messages, pad=">")

        self.logger.debug(log)

    def score[T: AttributeModel | HasName](self, scorers: Sequence[Scorer], item: T, other: T) -> float:
        """Scores the similarity between the given items."""
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

        if self.score_items_in_collections and isinstance(item, CollectionModel):
            items = list(item.iter_items) if isinstance(item, CollectionModel) else []
            others = list(item.iter_items) if isinstance(item, CollectionModel) else []
            self._log_score_items(item, items, others)

            collection_scores = self._score_items(items, others)
            scores.extend(collection_scores)
            weight += item.count

        return sum(scores) / weight

    def _score_items[T: AttributeModel | HasName](self, items: Sequence[T], others: Sequence[T]) -> list[float]:
        scores = []
        others = list(copy(others))  # safely mutable

        for item in items:
            scorers = self.get_scorers_for_item(item)
            self._log_scorers(scorers, item=item, others=others)

            score = 0

            for i, other in enumerate(others):
                score = self.score(scorers, item=item, other=other)

                if score >= self.max_score:  # break early if a good enough match is found
                    others.pop(i)  # remove the matched track to prevent it from being matched again
                    break

            scores.append(score)

        return scores

    def _log_score_items[T: AttributeModel | HasName](
            self, item: Any, items: Collection[T], others: Collection[T]
    ) -> None:
        messages = [f"ITEMS: {len(items)}", f"OTHERS: {len(others)}"]

        if not items or not others:
            log = self._format_item_message(method="SKIP", item=item, messages=messages, pad=" ")
            self.logger.debug(log)
            return

        log = self._format_item_message(method="ITEMS", item=item, messages=messages, pad=" ")
        self.logger.debug(log)
