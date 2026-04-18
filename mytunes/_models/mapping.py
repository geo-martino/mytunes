from collections.abc import Iterable, Iterator, Mapping, MutableMapping, Hashable
from typing import Self, Any, get_args

from pydantic import GetCoreSchemaHandler, validate_call
from pydantic_core import core_schema, CoreSchema

from mytunes._models import ResourceModel
from mytunes.exception import MyTunesKeyError, MyTunesValidationError


class UniqueMapping[TK, TV: ResourceModel](Mapping[TK | TV, TV]):
    """Stores :py:class:`ResourceModel` items mapped according to their unique keys."""
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
            core_schema.dict_schema(keys_schema, values_schema),
            core_schema.set_schema(values_schema),
            core_schema.tuple_variable_schema(values_schema),
            core_schema.list_schema(values_schema),
        ])

        # noinspection PyProtectedMember
        return core_schema.no_info_after_validator_function(
            function=cls._construct,
            schema=handler(schema),
            serialization=core_schema.plain_serializer_function_ser_schema(lambda x: x._items)
        )

    @classmethod
    def _construct(cls, value: Self | Iterable[TV] | Mapping[Any, TV]) -> Self:
        if isinstance(value, cls):
            return value
        if isinstance(value, ResourceModel):
            return cls((value,))
        if isinstance(value, Mapping):
            return cls(value.values())
        if isinstance(value, Iterable):
            return cls(value)
        raise MyTunesValidationError(f"Unrecognised value type: {value!r}")

    def __init__(self, items: Iterable[TV] = None):
        if items is None:
            items = ()
        elif isinstance(items, Mapping):
            items = items.values()

        self._items: dict[TK | TV, TV] = {key: item for item in items for key in item.unique_keys}

    def __repr__(self):
        return repr(self._items)

    def __len__(self):
        return len(self._items)

    def __iter__(self):
        return iter(self._items)

    def __eq__(self, other: Self):
        if self is other:
            return True
        elif isinstance(other, Mapping):
            return self._items == other
        elif not isinstance(other, type(self)):
            return super().__eq__(other)

        return not (self.keys() - other.keys())

    def __ne__(self, other: Self):
        return not self.__eq__(other)

    # @validate_call  # not currently working with generics
    def __contains__(self, __item: TK | TV | Iterable[TK | TV]) -> bool:
        if isinstance(__item, ResourceModel):
            return any(key in self._items for key in __item.unique_keys)
        if isinstance(__item, Hashable) and __item in self._items:
            return True
        if isinstance(__item, Iterable) and not isinstance(__item, str):
            return all(item in self for item in __item)
        # last resort: iteration is a slow comparison on large collections
        return any(__item == i for i in self._items.values())

    @validate_call
    def __getitem__(self, __key: TK | TV) -> TV:
        if not isinstance(__key, ResourceModel):
            return self._items[__key]

        try:
            return next(self._items[key] for key in __key.unique_keys if key in self._items)
        except StopIteration:
            raise MyTunesKeyError(
                f"No items found for the model with keys: {", ".join(map(str, __key.unique_keys))}"
            )

    @property
    def unique(self) -> Iterator[TV]:
        """The unique items in this sequence"""
        seen = set()
        for key, value in self._items.items():
            if key in seen or any(key in seen for key in value.unique_keys):
                continue

            yield value
            seen.add(key)
            seen.update(value.unique_keys)

    @property
    def count(self) -> int:
        """The number of unique items in this sequence"""
        return len(list(self.unique))

    def copy(self) -> Self:
        """Return a shallow copy of this mapping"""
        return type(self)(self._items.copy())

    def _update(self, __m: Iterable[TV] | Mapping[TK | TV, TV], extract_keys: bool = True) -> None:
        """
        Merge this mapping with another mapping or iterable of items.
        This allows for privately updating the mapping with a new set of items,
        without exposing the full update interface to users.
        """
        if extract_keys:
            if isinstance(__m, Mapping):
                __m = __m.values()
            # noinspection PyTypeChecker
            __m = dict((key, item) for item in __m for key in item.unique_keys)

        self._items.update(dict(__m))

    def _replace(self, __m: Iterable[TV] | Mapping[TK | TV, TV], extract_keys: bool = True) -> None:
        """
        Replace all items in this mapping with another mapping or iterable of items.
        This allows for privately replacing the mapping with a new set of items,
        without exposing the full replace interface to users.
        """
        self._items.clear()
        self._update(__m, extract_keys=extract_keys)


class MutableUniqueMapping[TK, TV: ResourceModel](UniqueMapping[TK, TV], MutableMapping[TK | TV, TV]):
    """Stores :py:class:`ResourceModel` items mapped according to their unique keys."""
    @validate_call
    def __setitem__(self, __key: TK, __value: TV):
        # noinspection PyArgumentList
        self.add(__value)  # ignore the given key

    @validate_call
    def __delitem__(self, __key: TK):
        item = self[__key]
        # noinspection PyArgumentList
        self.remove(item)

    @validate_call
    def add(self, __item: TV) -> None:
        """Add an item to this mapping"""
        # noinspection PyTypeChecker
        for key in __item.unique_keys:
            self._items[key] = __item

    @validate_call
    def update(self, __m: Mapping[TK | TV, TV] | Iterable[TV], extract_keys: bool = True, **kwargs) -> None:
        """Merge this mapping with another mapping or iterable of items"""
        self._update(__m, extract_keys=extract_keys)

    @validate_call
    def remove(self, __item: TV) -> None:
        """Remove one item from this mapping"""
        # noinspection PyTypeChecker
        for key in __item.unique_keys:
            if key in self._items:
                del self._items[key]

    # WORKAROUND: we shouldn't need to define this manually as it's already defined in the parent class,
    #  but it seems to cause a recursion error when trying to call clear() from replace() without it...
    def clear(self) -> None:
        """Remove all items from this mapping"""
        self._items.clear()

    @validate_call
    def replace(self, __m: Mapping[TK | TV, TV] | Iterable[TV], extract_keys: bool = True) -> None:
        """Replace all items in this mapping with another mapping or iterable of items"""
        self._replace(__m, extract_keys=extract_keys)
