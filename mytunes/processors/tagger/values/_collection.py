from abc import abstractmethod
from collections.abc import Iterable
from typing import Any

from pydantic import Field, model_validator

from ._base import Value
from ..._types import _ATTRIBUTE_FIELD_TYPE
from ...._base.attribute import AttributeModel


# noinspection PyAbstractClass
class CollectionValue[IT: AttributeModel, VT: Any](Value[Iterable[IT], VT]):
    field: _ATTRIBUTE_FIELD_TYPE = Field(
        description="The field from which to get a tag value from.",
    )

    @model_validator(mode="before")
    @classmethod
    def _from_field[T](cls, data: T | str) -> T | dict[str, Any]:
        if not isinstance(data, str):
            return data
        return dict(field=data)

    @abstractmethod
    def get(self, items: Iterable[IT]) -> VT:
        """Get the value from a collection of items."""
        raise NotImplementedError

    def _get_values(self, items: Iterable[IT]) -> list[VT]:
        values = (getattr(item, self.field) for item in items)
        return list(filter(None, values))


class MinValue[IT: AttributeModel, VT: Any](CollectionValue[IT, VT]):
    def get(self, items: Iterable[IT]) -> VT | None:
        values = self._get_values(items)
        return min(values) if values else None


class MaxValue[IT: AttributeModel, VT: Any](CollectionValue[IT, VT]):
    def get(self, items: Iterable[IT]) -> VT | None:
        values = self._get_values(items)
        return max(values) if values else None
