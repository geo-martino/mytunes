from abc import abstractmethod
from collections.abc import Collection

from .._base import Processor


# noinspection PyAbstractClass
class Filter[IT](Processor):
    """Base class for all filters."""

    @property
    @abstractmethod
    def ready(self) -> bool:
        """Indicates if the filter is set and ready to be used."""
        raise NotImplementedError

    def __bool__(self) -> bool:
        return self.ready

    @abstractmethod
    def check(self, item: IT, *args, **kwargs) -> bool:
        """
        Check if the filter applies to the given item.

        :param item: The item to check against the filter.
        :return: A boolean indicating if the item matches the filter.
        """
        raise NotImplementedError

    def apply(self, items: Collection[IT], *args, **kwargs) -> list[IT]:
        """
        Apply the filter to the given items.

        :param items: The items to filter.
        :return: A sequence of items that match the filter.
        """
        if not self.ready:  # always return all items if filter is not setup
            return list(items)

        def _filter(item: IT) -> bool:
            return self.check(item, *args, **kwargs)
        return list(filter(_filter, items))
