from abc import ABCMeta, abstractmethod
from typing import Any

from musify.models import AttributeModel
from musify.processors_new import Processor


class TagCleaner[I: AttributeModel, T: Any](Processor, metaclass=ABCMeta):
    @abstractmethod
    def clean(self, item: I | T | None) -> T:
        """Cleans the given tag from the item and returns the cleaned tag."""
        raise NotImplementedError

    @abstractmethod
    def _get_item_value(self, item: I | None) -> T:
        """Get the value from the given item."""
        raise NotImplementedError
