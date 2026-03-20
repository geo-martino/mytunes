from abc import abstractmethod
from typing import Any

from pydantic import Field

from musify.models.properties.logger import HasLogger
from musify.models.properties.name import HasName
from musify.processors_new import Processor
from musify.processors_new.clean import TagCleaner


# noinspection PyAbstractClass
class Scorer[C: TagCleaner](Processor, HasLogger):
    """Scores the similarity between two items based on a specific tag."""

    type: str = Field(
        description="The type of score this is.",
    )
    cleaner: C = Field(
        description="The cleaner to use for cleaning the tag value before scoring.",
    )
    weight: int | float = Field(
        description="The weight to be applied to the score.",
        default=1,
    )
    required: bool = Field(
        description=(
            "Whether this scorer is required for a match. "
            "If True, the score must be above the max score threshold for a match "
            "regardless of the aggregate score with other scorer."
        ),
        default=False,
    )

    def can_score(self, item: Any) -> bool:
        """Check whether the item is scorable by this scorer."""
        return self.cleaner.can_clean(item)

    def score[T: HasName](self, item: T, other: T | None = None) -> int | float:
        """Scores the similarity between the source and other attributes."""
        item_val = self.cleaner.clean(item)
        other_val = self.cleaner.clean(other) if other is not None else None

        score = self._calculate_score(item_val, other_val) * self.weight

        self._log_score(item=item, result=score, item_val=item_val, other_val=other_val)
        return score

    @abstractmethod
    def _calculate_score[T: Any](self, value: T, other: T | None) -> int | float:
        """Scores the similarity between the value and other value without applying the weight."""
        raise NotImplementedError

    def _log_score[T: HasName](
            self,
            item: T,
            result: Any,
            item_val: Any,
            other_val: Any = None,
            method: str = "SCORE",
    ) -> None:
        """Wrapper for initially logging a score in a uniform aligned format"""
        result = self._clean_log_value(result)
        item_val = self._clean_log_value(item_val)
        other_val = self._clean_log_value(other_val)

        messages = [f"{self.type:>14}={result:<10}"]
        if not other_val:
            messages.append(item_val)
        else:
            messages.append(f"{item_val!r} -> {other_val!r}")

        log = self._format_item_message(method=method, item=item, messages=messages)
        self.logger.debug(log)

    @staticmethod
    def _clean_log_value[T](value: T) -> T:
        match value:
            case float():
                value = round(value, 2)
        return value
