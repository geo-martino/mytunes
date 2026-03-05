from abc import abstractmethod
from typing import Any

from musify.exception import MusifyValueError
from musify.models import AttributeModel
from musify.processors_new import Processor


# noinspection PyAbstractClass
class TagCleaner[I: AttributeModel, T: Any](Processor):
    @classmethod
    @abstractmethod
    def can_clean(cls, item: Any) -> bool:
        """Check whether the item can be cleaned by this cleaner."""
        raise NotImplementedError

    @abstractmethod
    def clean(self, item: I | T | None) -> T:
        """Cleans the given tag from the item and returns the cleaned tag."""
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def _get_item_value(cls, item: I | None) -> T:
        """Get the value from the given item."""
        raise MusifyValueError(f"Cannot clean item of type {type(item)} with {cls.__class__.__name__}")
