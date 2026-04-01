from __future__ import annotations

from collections.abc import Iterable, Sequence
from functools import total_ordering
from typing import ClassVar, Any, Self

from pydantic import PrivateAttr, ValidationError

from musify._types import String, Number
from musify.models._attribute import AttributeModel
from musify.models._base import RootModel


@total_ordering
class NumberModel[T: Number](RootModel[T]):
    def __int__(self):
        return int(self.root)

    def __float__(self):
        return float(self.root)

    def __hash__(self) -> int:
        return hash(self.root)

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, str):
            try:
                other = self.model_validate(other)
            except ValidationError:
                return False

        return other is not None and self.root == float(other)

    def __lt__(self, other: Any) -> bool:
        if isinstance(other, str):
            try:
                other = self.model_validate(other)
            except ValidationError:
                return False

        return other is not None and self.root < float(other)

    def __add__(self, other: Any) -> Self:
        other = self.model_validate(other)
        return self.model_validate(self.root + float(other))

    def __sub__(self, other: Any) -> Self:
        other = self.model_validate(other)
        return self.model_validate(self.root - float(other))

    def __mul__(self, other: Any) -> Self:
        other = self.model_validate(other)
        return self.model_validate(self.root * float(other))

    def __truediv__(self, other: Any) -> Self:
        other = self.model_validate(other)
        return self.model_validate(self.root / float(other))


class HasSeparableTags(AttributeModel):
    """Represents a resource that has a tag separator."""
    _tag_sep: ClassVar[Sequence[String]] = PrivateAttr(
        # description="The separator used to separate tags in this resource.",
        default=("; ", "\x00"),  # also split string values on null
    )

    @classmethod
    def _join_tags(cls, tags: Iterable[Any]) -> str:
        sep = next(iter(cls._tag_sep))
        return sep.join(map(str, tags))

    @classmethod
    def _separate_tags(cls, tags: str) -> list[str]:
        seps = iter(cls._tag_sep)
        tags = tags.split(next(seps))
        for sep in seps:
            tags = [t for tag in tags for t in tag.rstrip(sep).split(sep)]

        return [tag for tag in tags if tag]
