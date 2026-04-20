from __future__ import annotations

from functools import total_ordering
from typing import Any, Self

from pydantic import ValidationError, ConfigDict

from mytunes._types import Number
from .._base import RootModel


@total_ordering
class NumberModel[T: Number](RootModel[T]):
    model_config = ConfigDict(frozen=True)

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
