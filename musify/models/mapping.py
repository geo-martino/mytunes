from collections.abc import Iterable, Mapping, MutableMapping, Hashable
from typing import Self, Any, get_args

from pydantic import GetCoreSchemaHandler, validate_call
from pydantic_core import core_schema

from musify.exception import MusifyKeyError, MusifyTypeError
from musify.models import MusifyResource


class MusifyMapping[TK, TV: MusifyResource](Mapping[TK | TV, TV]):
    """Stores :py:class:`MusifyResource` items mapped according to their unique keys."""
    # noinspection PyUnusedLocal
    @classmethod
    def __get_pydantic_core_schema__(cls, source: Any, handler: GetCoreSchemaHandler) -> core_schema.CoreSchema:
        args = get_args(source)
        if args:
            keys_schema = handler.generate_schema(args[0])
            values_schema = handler.generate_schema(args[1])
        else:
            keys_schema = core_schema.any_schema()
            values_schema = core_schema.is_instance_schema(MusifyResource)

        schema = core_schema.union_schema([
            core_schema.is_instance_schema(cls),
            values_schema,
            core_schema.dict_schema(keys_schema, values_schema),
            core_schema.set_schema(values_schema),
            core_schema.tuple_variable_schema(values_schema),
            core_schema.list_schema(values_schema),
        ])

        return core_schema.no_info_after_validator_function(
            function=cls._construct,
            schema=handler(schema),
            serialization=core_schema.plain_serializer_function_ser_schema(lambda x: x._items)
        )

    @classmethod
    def _construct(cls, value: Self | Iterable[TV] | Mapping[Any, TV]) -> Self:
        if isinstance(value, cls):
            return value
        if isinstance(value, MusifyResource):
            return cls((value,))
        if isinstance(value, Mapping):
            return cls(value.values())
        if isinstance(value, Iterable):
            return cls(value)
        raise MusifyTypeError(f"Unrecognised value type: {value!r}")

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
        elif not isinstance(other, self.__class__):
            return super().__eq__(other)

        return not (self.keys() - other.keys())

    def __ne__(self, other: Self):
        return not self.__eq__(other)

    @validate_call
    def __contains__(self, __item: TK | TV | Iterable[TK | TV]) -> bool:
        if isinstance(__item, MusifyResource):
            return any(key in self._items for key in __item.unique_keys)
        if isinstance(__item, Iterable):
            return all(item in self for item in __item)
        if isinstance(__item, Hashable) and __item in self._items:
            return True
        # last resort: iteration is a slow comparison on large collections
        return any(__item == i for i in self._items.values())

    @validate_call
    def __getitem__(self, __key: TK | TV) -> TV:
        if not isinstance(__key, MusifyResource):
            return self._items[__key]

        try:
            return next(self._items[key] for key in __key.unique_keys if key in self._items)
        except StopIteration:
            raise MusifyKeyError(
                f"No items found for the model with keys: {", ".join(map(str, __key.unique_keys))}"
            )

    def copy(self) -> Self:
        """Return a shallow copy of this mapping"""
        return self.__class__(self._items.copy())


class MusifyMutableMapping[TK, TV: MusifyResource](MusifyMapping[TK, TV], MutableMapping[TK | TV, TV]):
    """Stores :py:class:`MusifyResource` items mapped according to their unique keys."""
    @validate_call
    def __setitem__(self, __key: TK, __value: TV):
        self.add(__value)  # ignore the given key

    @validate_call
    def __delitem__(self, __key: TK):
        item = self[__key]
        self.remove(item)

    @validate_call
    def add(self, __item: TV) -> None:
        """Add an item to this mapping"""
        # noinspection PyTypeChecker
        for key in __item.unique_keys:
            self._items[key] = __item

    @validate_call
    def update(self, __m: Iterable[TV] | Mapping[TK | TV, TV], **kwargs) -> None:
        """Merge this mapping with another mapping or iterable of items"""
        if isinstance(__m, Mapping):
            __m = __m.values()

        items = dict((key, item) for item in __m for key in item.unique_keys)
        self._items.update(items)

    @validate_call
    def remove(self, __item: TV) -> None:
        """Remove one item from this mapping"""
        # noinspection PyTypeChecker
        for key in __item.unique_keys:
            if key in self._items:
                del self._items[key]
