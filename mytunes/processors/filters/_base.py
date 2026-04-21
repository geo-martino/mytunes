from abc import abstractmethod
from collections.abc import Collection
from typing import Annotated

from pydantic import Discriminator, Field

from .._base import Processor
from ..._base.discriminator import DiscriminatorModel, DiscriminatorAttribute


# noinspection PyAbstractClass
class Filter[FT: str, IT](Processor, DiscriminatorModel):
    """Base class for all filters."""

    type: Annotated[FT, DiscriminatorAttribute()] = Field(
        description="The type of this filter."
    )

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
