from collections.abc import Mapping, Iterable, Sequence, MutableSequence, Iterator
from typing import Any, Self, overload, get_args

from mytunes.core.mapping import MutableUniqueMapping
from mytunes.exception import MyTunesValidationError
from pydantic import GetCoreSchemaHandler, validate_call, ConfigDict
from pydantic_core import core_schema, CoreSchema

from .._base.resource import ResourceModel


class UniqueSequence[TK, TV: ResourceModel](Sequence[TV]):
    """
    Stores :py:class:`ResourceModel` items with optimisations
    to execute functionality on the sequence according to the item's unique keys.
    """
    # noinspection PyUnusedLocal
    @classmethod
    def __get_pydantic_core_schema__(cls, source: Any, handler: GetCoreSchemaHandler) -> CoreSchema:
        args = get_args(source)
        if args:
            keys_schema = handler.generate_schema(args[0])
            values_schema = handler.generate_schema(args[1])
        else:
            keys_schema = core_schema.any_schema()
            values_schema = core_schema.is_instance_schema(ResourceModel)

        schema = core_schema.union_schema([
            core_schema.is_instance_schema(cls),
            values_schema,
            core_schema.dict_schema(keys_schema=keys_schema, values_schema=values_schema),
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

    def __init__(self, items: Iterable[TV] | Mapping[Any, TV] = None):
        if items is None:
            items = ()
        elif isinstance(items, Mapping):
            items = items.values()

        self._items_mapped: MutableUniqueMapping[TK, TV] = MutableUniqueMapping(items)

    def __repr__(self):
        return repr(f"{type(self).__name__}(count={len(self)})")

    def __len__(self):
        return self._items_mapped.count

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
    def __contains__(self, __item: TK | TV | Iterable[TK | TV]) -> bool:
        return __item in self._items_mapped

    @overload
    def __getitem__(self, index: int) -> TV: ...

    @overload
    def __getitem__(self, index: slice) -> list[TV]: ...

    @validate_call(config=ConfigDict(arbitrary_types_allowed=True))
    def __getitem__(self, index: int | slice | TK | TV) -> TV | list[TV]:
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

    @property
    def unique(self) -> Iterator[TV]:
        """The unique items in this sequence"""
        yield from self._items_mapped.unique

    def get(self, key: TK | TV, default: TV | None = None) -> TV | None:
        """Get an item by its key, returning `default` if not found."""
        return self._items_mapped.get(key, default)

    def copy(self) -> Self:
        """Return a shallow copy of this sequence"""
        return type(self)(self.unique)

    def _extend(self, __iterable: Iterable[TV]) -> None:
        """
        Add many items to the end of this sequence.
        This allows for privately extending the sequence with a new set of items,
        without exposing the full extending interface to users.
        """
        self._items_mapped.update(__iterable)

    def _replace(self, __m: Iterable[TV] | Mapping[TK | TV, TV]) -> None:
        """
        Replace all items in this sequence.
        This allows for privately replacing the sequence with a new set of items,
        without exposing the full sequence interface to users.
        """
        self._items_mapped.replace(__m)

    @validate_call
    def intersection(self, other: Sequence[TV] | set[TV]) -> tuple[TV, ...]:
        """
        Return the intersection between the items in this collection and an ``other`` collection as a new list.

        (i.e. all items that are in both this collection and the ``other`` collection).
        """
        return tuple(item for item in self if item in other)

    @validate_call
    def difference(self, other: Sequence[TV] | set[TV]) -> tuple[TV, ...]:
        """
        Return the difference between the items in this collection and an ``other`` collection as a new list.

        (i.e. all items that are in this collection but not the ``other`` collection).
        """
        return tuple(item for item in self if item not in other)

    @validate_call
    def outer_difference(self, other: Sequence[TV] | set[TV]) -> tuple[TV, ...]:
        """
        Return the outer difference between the items in this collection and an ``other`` collection as a new list.

        (i.e. all items that are in the ``other`` collection but not in this collection).
        """
        return tuple(item for item in other if item not in self)


class MutableUniqueSequence[TK, TV: ResourceModel](UniqueSequence[TK, TV], MutableSequence[TV]):
    """
    Stores :py:class:`ResourceModel` items with optimisations
    to execute functionality on the sequence according to the item's unique keys.
    """
    @overload
    def __setitem__(self, index: int, value: TV) -> None: ...

    @overload
    def __setitem__(self, index: slice, value: Iterable[TV]) -> None: ...

    @validate_call(config=ConfigDict(arbitrary_types_allowed=True))
    def __setitem__(self, index: int | slice, value: TV | Iterable[TV]):
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
    def __add__(self, other: Iterable[TV]):
        items = self.copy()
        # noinspection PyArgumentList
        items.extend(other)
        return items

    @validate_call
    def __iadd__(self, other: Iterable[TV]):
        # noinspection PyArgumentList
        self.extend(other)
        return self

    @validate_call
    def __sub__(self, other: Iterable[TV]):
        items = self.copy()
        # noinspection PyArgumentList
        items.remove(other)
        return items

    @validate_call
    def __isub__(self, other: Iterable[TV]):
        # noinspection PyArgumentList
        self.remove(other)
        return self

    @validate_call
    def __or__(self, other: Sequence[TV]) -> Self:
        items = self.copy()
        # noinspection PyArgumentList
        items.merge(other)
        return items

    @validate_call
    def __ior__(self, other: Sequence[TV]) -> Self:
        # noinspection PyArgumentList
        self.merge(other)
        return self

    @validate_call
    def append(self, __object: TV) -> None:
        """Add an item to the end of this sequence"""
        self._items_mapped.add(__object)

    @validate_call
    def extend(self, __iterable: Iterable[TV]) -> None:
        """Add many items to the end of this sequence"""
        self._extend(__iterable)

    @validate_call
    def insert(self, __index: int, __object: TV) -> None:
        """Insert the item at the given index"""
        items = list(self._items_mapped.unique)
        items.insert(__index, __object)
        self._items_mapped.replace(items)

    # noinspection PyArgumentList
    @validate_call
    def merge(self, other: Sequence[TV], reference: Sequence[TV] | None = None) -> None:
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
    def remove(self, __value: TV | Iterable[TV]) -> None:
        """Remove one item from this sequence"""
        if isinstance(__value, ResourceModel):
            __value = (__value,)

        for item in __value:
            del self._items_mapped[item]

    def clear(self) -> None:
        """Remove all items from this sequence"""
        self._items_mapped.clear()

    # @validate_call  # doesn't work with Iterables
    def replace(self, __iterable: Iterable[TV]) -> None:
        """Replace all items in this sequence"""
        self._replace(__iterable)

    def sort(self, key=None, reverse: bool = False) -> None:
        """Sort the items in this sequence in place"""
        items = sorted(self.unique, key=key, reverse=reverse)
        self._items_mapped.replace(items)
