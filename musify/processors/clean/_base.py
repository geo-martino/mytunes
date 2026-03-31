from abc import abstractmethod
from typing import Any

from musify.exception import MusifyTypeError
from musify.models import AttributeModel
from musify.processors import Processor


# noinspection PyAbstractClass
class TagCleaner[IT: AttributeModel, VT: Any](Processor):
    @classmethod
    @abstractmethod
    def can_clean(cls, item: Any, skip_on_exact_type: bool = False) -> bool:
        """
        Check whether the item can be cleaned by this cleaner.

        :param item: The item to clean.
        :param skip_on_exact_type: Whether to mark as False if the given item is an exact type match for this cleaner.
            This can be used in cases where another scorer will handle this item to avoid scoring twice.
        """
        raise NotImplementedError

    @abstractmethod
    def clean(self, item: IT | VT | None) -> VT:
        """Cleans the given tag from the item and returns the cleaned tag."""
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def _get_item_value(cls, item: IT | None) -> VT:
        """Get the value from the given item."""
        raise MusifyTypeError(f"Cannot clean item of type {type(item)} with {cls.__name__}")
