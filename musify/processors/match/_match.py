from collections.abc import Sequence, Collection
from copy import copy
from typing import Any

from pydantic import conlist, Field

from musify.models import AttributeModel
from musify.models.collection import CollectionModel
from musify.models.properties.logger import HasLogger
from musify.models.properties.name import HasName
from musify.processors import Processor
from musify.processors.match.score import Scorer


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

        other = None
        for other in others:
            other_value = self._get_item_log_value(other)
            log = self._format_item_message(method="ITEM", item=item, messages=other_value, pad="-")
            self.logger.debug(log)

            score = self.score(item=item, other=other, scorers=scorers)
            if score > self.min_score and score > best_score:
                best_match = other
                best_score = score

            if score >= self.max_score:  # break early if a good enough match is found
                break

            messages = [other_value, f"SCORE={score:.2f}"]
            log = self._format_item_message(method="SUM", item=item, messages=messages, pad="-")
            self.logger.debug(log)

        messages = [self._get_item_log_value(best_match or other), f"SCORE={best_score:.2f}"]
        if best_score <= self.min_score:
            method = "FAILED"
            messages.append(f"< MIN SCORE ({self.min_score:.2f})")
        elif best_score >= self.max_score:
            method = "MATCHED"
            messages.append(f"> MAX SCORE ({self.max_score:.2f})")
        else:
            method = "MATCHED"
            messages.append("= BEST SCORE")

        log = self._format_item_message(method=method, item=item, messages=messages, pad="<")
        self.logger.debug(log)
        return best_match  # will be None if no match above min_score was found

    def _log_scorers(self, scorers: list[Scorer], item: Any, others: Collection) -> None:
        """Log the scorers being used for a given item and other item."""
        required = [scorer for scorer in scorers if scorer.required_score > 0]
        optional = [scorer for scorer in scorers if scorer.required_score == 0]
        messages = [
            f"ITEMS: {len(others)}",
            f"REQUIRED: {", ".join(f"{scorer.type}>={scorer.required_score}" for scorer in required)}"
            if required else "No required scorers",
            f"OPTIONAL: {", ".join(scorer.type for scorer in optional)}"
            if optional else "No optional scorers",
        ]
        log = self._format_item_message(method="START", item=item, messages=messages, pad=">")

        self.logger.debug(log)

    def score[T: AttributeModel | HasName](
            self, item: T, other: T, scorers: Sequence[Scorer] | None = None, score_items_in_collections: bool = True
    ) -> float:
        """Scores the similarity between the given items."""
        if scorers is None:
            scorers = self.get_scorers_for_item(item)

        scores = []
        weight = sum(scorer.weight for scorer in scorers)

        # apply required scorers first to allow for early stopping if they fail
        for scorer in filter(lambda x: x.required_score > 0, scorers):
            score = scorer.score(item, other)
            if score < scorer.required_score:
                message = ["SCORER FAILED".ljust(25), f"{scorer.type}={score:.2f} < {scorer.required_score:.2f}"]
                log = self._format_item_message(method="SKIP", item=item, messages=message, pad="<")
                self.logger.debug(log)
                return 0

            scores.append(score)

        scores.extend(scorer.score(item, other) for scorer in filter(lambda x: x.required_score == 0, scorers))

        if score_items_in_collections and self.score_items_in_collections and isinstance(item, CollectionModel):
            items = list(item.items) if isinstance(item, CollectionModel) else []
            others = list(other.items) if isinstance(other, CollectionModel) else []
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
                score = self.score(item=item, other=other, scorers=scorers, score_items_in_collections=False)

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
            log = self._format_item_message(method="SKIP", item=item, messages=messages)
            self.logger.debug(log)
            return

        log = self._format_item_message(method="ITEMS", item=item, messages=messages)
        self.logger.debug(log)
