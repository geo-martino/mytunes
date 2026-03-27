"""
Basic concrete implementation of a MusifyCollection.
"""
from __future__ import annotations

from collections.abc import Iterable, Collection
from typing import Any

from musify.base import MusifyItem
from musify.libraries.core.collection import MusifyCollection
from musify.utils import to_collection


class BasicCollection[T: MusifyItem](MusifyCollection[T]):
    """
    A basic implementation of MusifyCollection for storing ``items`` with a given ``name``.

    :param name: The name of this collection.
    :param items: The items in this collection
    """

    __slots__ = ("_name", "_items")

    @staticmethod
    def _validate_item_type(items: Any | Iterable[Any]) -> bool:
        if isinstance(items, Iterable):
            return all(isinstance(item, MusifyItem) for item in items)
        return isinstance(items, MusifyItem)

    @property
    def name(self):
        """The name of this collection"""
        return self._name

    @property
    def items(self) -> list[T]:
        return self._items

    @property
    def length(self):
        lengths = {getattr(item, "length", None) for item in self.items}
        return sum({length for length in lengths if length}) if lengths else None

    def __init__(self, name: str, items: Collection[T], *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._name = name
        self._items = to_collection(items, list)
