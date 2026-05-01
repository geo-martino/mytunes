from collections.abc import Mapping, Iterable, Sequence, MutableSequence, Iterator
from typing import Any, Self, overload, get_args

from pydantic import GetCoreSchemaHandler, validate_call, ConfigDict, OnErrorOmit
from pydantic_core import core_schema, CoreSchema

from mytunes.core.mapping import MutableUniqueMapping
from mytunes.exception import MyTunesValidationError
from .._base.resource import ResourceModel


class UniqueSequence[IT: ResourceModel](Sequence[IT]):
    """
    Stores :py:class:`ResourceModel` items with optimisations
    to execute functionality on the sequence according to the item's unique keys.
    """
    # noinspection PyUnusedLocal
    @classmethod
    def __get_pydantic_core_schema__(cls, source: Any, handler: GetCoreSchemaHandler) -> CoreSchema:
        args = get_args(source)
        if args:
            values_schema = handler.generate_schema(args[0])
        else:
            values_schema = core_schema.is_instance_schema(ResourceModel)

        schema = core_schema.union_schema([
            core_schema.is_instance_schema(cls),
            values_schema,
            core_schema.set_schema(values_schema),
            core_schema.tuple_variable_schema(values_schema),
            core_schema.list_schema(values_schema),
        ])

        # noinspection PyProtectedMember
        return core_schema.no_info_after_validator_function(
            function=cls._construct,
            schema=handler(schema),
            serialization=core_schema.plain_serializer_function_ser_schema(lambda x: list(x.unique))
        )

    @classmethod
    def _construct(cls, value: Any) -> Self:
        match value:
            case cls():
                return value
            case ResourceModel():
                return cls((value,))
            case Iterable():
                return cls(value)
        raise MyTunesValidationError(f"Invalid value: {value}")

    def __init__(self, items: Iterable[IT] | Mapping[Any, IT] = None):
        if items is None:
            items = ()
        elif isinstance(items, Mapping):
            items = items.values()

        self._items_mapped: MutableUniqueMapping[Any, IT] = MutableUniqueMapping(items)

    def __repr__(self):
        return repr(f"{type(self).__name__}(count={len(self)})")

    def __len__(self):
        return self._items_mapped.total

    def __iter__(self):
        return self.unique

    def __eq__(self, other: Self):
        """Matching type and all keys in this mapping present in the other mapping"""
        if self is other:
            return True
        elif isinstance(other, Sequence):
            return list(self.unique) == other
        elif not isinstance(other, type(self)):
            return super().__eq__(other)

        return self._items_mapped == other._items_mapped

    def __ne__(self, other: Self):
        return not self.__eq__(other)

    @validate_call
    def __contains__(self, __item: IT | Iterable[OnErrorOmit[IT | Any]] | Any) -> bool:
        return __item in self._items_mapped

    @overload
    def __getitem__(self, index: int) -> IT: ...

    @overload
    def __getitem__(self, index: slice) -> list[IT]: ...

    @validate_call(config=ConfigDict(arbitrary_types_allowed=True))
    def __getitem__(self, index: int | slice | IT | Any) -> IT | list[IT]:
        match index:
            case int() if index < len(self):
                items = enumerate(self._items_mapped.unique)
                if index < 0:
                    # TODO: this is inefficient, improve performance
                    items = reversed(list(items))

                current_idx, current_item = next(iter(items))
                while current_idx < index:
                    current_idx, current_item = next(iter(items))

                return current_item
            case slice():
                return list(self._items_mapped.unique)[index]
            case _:
                return self._items_mapped[index]

    @validate_call
    def __add__(self, other: Iterable[OnErrorOmit[IT]]):
        items = self.copy()
        # noinspection PyArgumentList
        items._extend(other)
        return items

    @validate_call
    def __sub__(self, other: Iterable[OnErrorOmit[IT]]):
        items = self.copy()
        # noinspection PyArgumentList
        for it in other:
            del items._items_mapped[it]
        return items

    @validate_call
    def __or__(self, other: Sequence[OnErrorOmit[IT]]) -> Self:
        items = self.copy()
        # noinspection PyArgumentList
        items._extend(other)
        return items


    @property
    def unique(self) -> Iterator[IT]:
        """The unique items in this sequence"""
        yield from self._items_mapped.unique

    def refresh(self) -> None:
        """
        Refresh the uniqueness of items in this sequence.
        Useful when the unique keys of items have changed since being added.
        """
        self._items_mapped.refresh()

    def get(self, key: IT | Any, default: IT | None = None) -> IT | None:
        """Get an item by its key, returning `default` if not found."""
        return self._items_mapped.get(key, default)

    def copy(self) -> Self:
        """Return a shallow copy of this sequence"""
        return type(self)(self.unique)

    def _extend(self, __iterable: Iterable[IT]) -> None:
        """
        Add many items to the end of this sequence.
        This allows for privately extending the sequence with a new set of items,
        without exposing the full extending interface to users.
        """
        self._items_mapped.update(__iterable)

    def _replace(self, __m: Iterable[IT] | Mapping[Any, IT]) -> None:
        """
        Replace all items in this sequence.
        This allows for privately replacing the sequence with a new set of items,
        without exposing the full sequence interface to users.
        """
        self._items_mapped.replace(__m)

    @validate_call
    def intersection(self, other: Sequence[OnErrorOmit[IT]] | set[OnErrorOmit[IT]]) -> tuple[IT, ...]:
        """
        Return the intersection between the items in this collection and an ``other`` collection as a new list.

        (i.e. all items that are in both this collection and the ``other`` collection).
        """
        return tuple(item for item in self if item in other)

    @validate_call
    def difference(self, other: Sequence[OnErrorOmit[IT]] | set[OnErrorOmit[IT]]) -> tuple[IT, ...]:
        """
        Return the difference between the items in this collection and an ``other`` collection as a new list.

        (i.e. all items that are in this collection but not the ``other`` collection).
        """
        return tuple(item for item in self if item not in other)

    @validate_call
    def outer_difference(self, other: Sequence[OnErrorOmit[IT]] | set[OnErrorOmit[IT]]) -> tuple[IT, ...]:
        """
        Return the outer difference between the items in this collection and an ``other`` collection as a new list.

        (i.e. all items that are in the ``other`` collection but not in this collection).
        """
        return tuple(item for item in other if item not in self)


class MutableUniqueSequence[IT: ResourceModel](UniqueSequence[IT], MutableSequence[IT]):
    """
    Stores :py:class:`ResourceModel` items with optimisations
    to execute functionality on the sequence according to the item's unique keys.
    """
    @overload
    def __setitem__(self, index: int, value: IT) -> None: ...

    @overload
    def __setitem__(self, index: slice, value: Iterable[IT]) -> None: ...

    @validate_call(config=ConfigDict(arbitrary_types_allowed=True))
    def __setitem__(self, index: int | slice, value: IT | Iterable[OnErrorOmit[IT]]):
        if isinstance(index, int):
            return self.insert(index, value)

        items = list(self._items_mapped.unique)
        items = items[index.start:] + list(value) + items[index.start:index.stop]
        self._replace(items)

    @validate_call(config=ConfigDict(arbitrary_types_allowed=True))
    def __delitem__(self, index: int | slice) -> None:
        # noinspection PyArgumentList
        self.remove(self[index])

    @validate_call
    def __iadd__(self, other: Iterable[OnErrorOmit[IT]]):
        # noinspection PyArgumentList
        self.extend(other)
        return self

    @validate_call
    def __isub__(self, other: Iterable[OnErrorOmit[IT]]):
        # noinspection PyArgumentList
        self.remove(other)
        return self

    @validate_call
    def __ior__(self, other: Sequence[OnErrorOmit[IT]]) -> Self:
        # noinspection PyArgumentList
        self.merge(other)
        return self

    @validate_call
    def append(self, __object: IT) -> None:
        """Add an item to the end of this sequence"""
        self._items_mapped.add(__object)

    @validate_call
    def extend(self, __iterable: Iterable[OnErrorOmit[IT]]) -> None:
        """Add many items to the end of this sequence"""
        self._extend(__iterable)

    @validate_call
    def insert(self, __index: int, __object: IT) -> None:
        """Insert the item at the given index"""
        items = list(self._items_mapped.unique)
        items.insert(__index, __object)
        self._items_mapped.replace(items)

    # noinspection PyArgumentList
    @validate_call
    def merge(self, other: Sequence[OnErrorOmit[IT]], reference: Sequence[OnErrorOmit[IT]] | None = None) -> None:
        """
        Merge this sequence with another collection.

        By providing just a collection of items, this function will add all new items (without duplicates)
        to the end of this sequence.

        Optionally, a 3-way sync may be achieved by providing a ``reference`` sequence to compare the current sequence
        and the ``other`` sequence to. Items present in both this sequence and the ``reference``
        but not in the ``other`` sequence will be removed from this sequence.

        :param other: The sequence of items to merge with.
        :param reference: The reference sequence to compare this sequence and the ``other`` sequence to.
        """
        if reference is None:
            # noinspection PyArgumentList
            self.extend(other)
            return

        self.remove(item for item in reference if item not in other and item in self)
        # noinspection PyTypeChecker
        self.extend(type(self).outer_difference(reference, other))

    @validate_call
    def remove(self, __value: IT | Iterable[OnErrorOmit[IT]]) -> None:
        """Remove one item from this sequence"""
        if isinstance(__value, ResourceModel):
            __value = (__value,)

        for item in __value:
            del self._items_mapped[item]

    def clear(self) -> None:
        """Remove all items from this sequence"""
        self._items_mapped.clear()

    @validate_call
    def replace(self, __iterable: Iterable[OnErrorOmit[IT]]) -> None:
        """Replace all items in this sequence"""
        self._replace(__iterable)

    def sort(self, key=None, reverse: bool = False) -> None:
        """Sort the items in this sequence in place"""
        items = sorted(self.unique, key=key, reverse=reverse)
        self._items_mapped.replace(items)
