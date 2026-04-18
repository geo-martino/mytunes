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
    def check(self, item: IT, reference: IT | None = None) -> bool:
        """
        Check if the filter applies to the given item.

        :param item: The item to check against the filter.
        :param reference: An optional reference to check against the item. Not used by all filters.
        :return: A boolean indicating if the item matches the filter.
        """
        raise NotImplementedError

    def apply(self, items: Collection[IT], reference: IT | None = None) -> list[IT]:
        """
        Apply the filter to the given items.

        :param items: The items to filter.
        :param reference: An optional reference to check against the items. Not used by all filters.
        :return: A sequence of items that match the filter.
        """
        if not self.ready:  # always return all items if filter is not setup
            return list(items)

        def _filter(item: IT) -> bool:
            return self.check(item, reference=reference)
        return list(filter(_filter, items))
