from abc import abstractmethod
from typing import Collection, Iterator, Any

from pydantic import Field, validate_call

from musify.processors.filters._base import Filter
from musify.processors.filters.values import ValuesFilter


class CompositeFilter[IT](Filter[IT], Collection[Filter[IT]]):
    """Composite filter which filters based on many :py:class:`Filter` objects"""

    @property
    @abstractmethod
    def filters(self) -> Collection[Filter]:
        """All filters configured."""
        raise NotImplementedError

    @property
    def ready(self):
        return any(filter_.ready for filter_ in self.filters)

    def __iter__(self) -> Iterator[Filter]:
        def flatten_filters(filter_: Filter | Collection[Filter]) -> Iterator[Filter]:
            """
            Get flat iterator for all :py:class:`Filter` objects in the given Filter,
            flattening out any :py:class:`FilterComposite` objects
            """
            if isinstance(filter_, CompositeFilter):
                return iter(filter_)
            return iter((filter_,))

        return (f for filter_ in self.filters for f in flatten_filters(filter_))

    def __len__(self):
        return len(self.filters)

    def __contains__(self, item: Any):
        return item in self.filters


class IncludeExcludeFilter[IT, IF: Filter, EF: Filter](CompositeFilter[IT]):
    include: IF = Field(
        description="Filter for items to include",
        default_factory=ValuesFilter,
    )
    exclude: EF = Field(
        description="Filter for items to exclude",
        default_factory=ValuesFilter,
    )

    @property
    def filters(self) -> Collection[Filter]:
        return self.include, self.exclude

    @validate_call
    def check(self, item: IT, *_, **__) -> bool:
        match = self.include.check(item)
        if self.exclude.ready:
            match &= not self.exclude.check(item)
        return match

    def __eq__(self, item: Any):
        return isinstance(item, self.__class__) and all((
            self.include == item.include,
            self.exclude == item.exclude
        ))
