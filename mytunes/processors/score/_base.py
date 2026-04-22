from abc import abstractmethod
from collections.abc import MutableMapping
from typing import Any, Annotated

from pydantic import Field, model_validator
from pydantic.fields import FieldInfo

from mytunes._types import Number
from mytunes.core.properties.logger import HasLogger
from mytunes.core.properties.name import HasName
from mytunes.processors.clean import TagCleaner
from .._base import Processor
from ..._base.discriminator import DiscriminatorModel, DiscriminatorAttribute


# noinspection PyAbstractClass
class Scorer[ST: str, CT: TagCleaner](Processor, DiscriminatorModel, HasLogger):
    """Scores the similarity between two items based on a specific tag."""

    type: Annotated[ST, DiscriminatorAttribute()] = Field(
        description="The type of score this is.",
    )
    cleaner: CT = Field(
        description="The cleaner to use for cleaning the tag value before scoring.",
    )
    weight: Number = Field(
        description="The weight to be applied to the score.",
        default=1,
    )
    required_score: float = Field(
        description=(
            "The minimum required score for this scorer to pass. "
            "The score for this scorer must be above this max score threshold for a match "
            "regardless of the aggregate score with other scorers. "
            "If the score is not above this threshold, no other scorers will be applied."
        ),
        default=0,
        ge=0,
        le=1,
    )

    @model_validator(mode="before")
    @classmethod
    def _add_cleaner_value[T](cls, data: T | MutableMapping[str, Any]) -> T | MutableMapping[str, Any]:
        if not isinstance(data, MutableMapping) or not cls.__final__:
            return data

        field: FieldInfo = cls.model_fields[key := "cleaner"]
        if not field.is_required() or cls._get_value_from_data(data, key) is not None:
            return data

        data[key] = field.annotation()
        return data

    def can_score(self, item: Any, skip_on_exact_type: bool = False) -> bool:
        """Check whether the item is scorable by this scorer."""
        return self.cleaner.can_clean(item, skip_on_exact_type=skip_on_exact_type)

    def score[T: HasName](self, item: T, other: T | None = None) -> Number:
        """Scores the similarity between the source and other attributes."""
        item_val = self.cleaner.clean(item)
        other_val = self.cleaner.clean(other) if other is not None else None

        score = self._calculate_score(item_val, other_val) * self.weight

        self._log_score(item=item, result=score, item_val=item_val, other_val=other_val)
        return score

    @abstractmethod
    def _calculate_score[T: Any](self, value: T, other: T | None) -> Number:
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

        messages = [f"{self.type:>14}={result:<5}"]
        if not other_val:
            messages.append(item_val)
        else:
            messages.append(f"{item_val!r} -> {other_val!r}")

        log = self._format_item_message(method=method, item=item, messages=messages)
        self._logger.debug(log)

    @staticmethod
    def _clean_log_value[T](value: T) -> T:
        match value:
            case float():
                value = round(value, 2)
        return value
