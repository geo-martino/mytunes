from abc import ABCMeta, abstractmethod
from typing import MutableSequence, Any

from pydantic import Field

from musify.models.properties.logger import HasLogger
from musify.models.properties.name import HasName
from musify.models.properties.uri import HasURI
from musify.processors_new import Processor
from musify.processors_new.match.clean import TagCleaner


class Scorer[C: TagCleaner](Processor, HasLogger, metaclass=ABCMeta):
    type: str = Field(
        description="The type of score this is. Used for logging and debugging purposes.",
    )
    cleaner: C = Field(
        description="The cleaner to use for cleaning the tag value before scoring.",
    )
    weight: int | float = Field(
        description="The weight to be applied to the score.",
        default=1,
    )

    def score[T: HasName](self, item: T, other: T | None = None) -> int | float:
        """Scores the similarity between the source and other attributes."""
        item_val = self.cleaner.clean(item)
        other_val = self.cleaner.clean(other) if other is not None else None

        score = self._calculate_score(item_val, other_val) * self.weight

        self._log_score(item=item, other=other, result=score, item_val=item_val, other_val=other_val)
        return score

    @abstractmethod
    def _calculate_score[T: Any](self, value: T, other: T | None) -> int | float:
        """Scores the similarity between the value and other value without applying the weight."""
        raise NotImplementedError

    def log(self, messages: MutableSequence[str], pad: str = ' ') -> None:
        """
        Log lists of ``messages`` in a uniform aligned format with a given ``pad`` character.

        Convenience function for ensuring consistent log format for results of operations of this class
        and any other classes which use this class.
        """
        messages[0] = pad * 3 + ' ' + (messages[0] if messages[0] else "unknown")
        self.logger.debug(" | ".join(messages))

    def _log_score[T: HasName](
            self,
            item: T,
            item_val: Any,
            result: Any,
            other: T | None = None,
            other_val: Any = None,
    ) -> None:
        """Wrapper for initially logging a score in a uniform aligned format"""
        if other is not None and isinstance(other, HasURI):
            log_result = f"> Scoring URI: {other.uri}"
        else:
            log_result = "> Score failed"

        if isinstance(result, float):
            result = round(result, 2)

        log = [item.name, log_result, f"{self.type:<10}={result:<5}"]
        if item_val or other_val:
            log.append(f"{item_val!r} -> {other_val!r}")

        self.log(log)
