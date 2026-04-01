"""
Processor that sorts the given collection of items based on given configuration.
"""
import re
from collections.abc import Mapping, MutableMapping, Sequence, Iterable, Collection, Iterator, MutableSequence
from copy import copy
from datetime import datetime
from random import random, randrange, shuffle, uniform
from typing import Any, Literal, Annotated

from pydantic import Field, field_validator, field_serializer

from musify._types import Number
from musify.exception import MusifyValueError, MusifyAttributeError
from musify.models import ResourceModel, IntEnumModel, AttributeModel
from musify.models.item.artist import HasArtists
from musify.models.item.track import Track
from musify.models.properties.audio import IsAudioFile
from musify.models.properties.date import HasAddedDate, HasPlayedDate
from musify.models.properties.file import IsLocalFile
from musify.models.properties.name import HasName
from musify.models.properties.rating import HasRating
from musify.processors._base import Processor

_SORT_TAG_TYPES: frozenset[type[AttributeModel]] = frozenset({
    Track,
    IsLocalFile,
    IsAudioFile,
    HasAddedDate,
    HasPlayedDate,
})
_SORT_FIELDS_MAP = {
    field: cls for cls in _SORT_TAG_TYPES for field in cls.__tag_attributes__
}
SORT_FIELDS = frozenset(_SORT_FIELDS_MAP)
_SORT_FIELDS_TYPE = Literal[*SORT_FIELDS]


class ShuffleMode(IntEnumModel):
    """Represents the possible shuffle modes to use when shuffling items using :py:class:`ItemSorter`."""
    NONE = 0
    RANDOM = 1
    HIGHER_RATING = 2
    RECENT_ADDED = 3
    DIFFERENT_ARTIST = 4


class ItemSorter(Processor):
    """
    Sort items in-place based on given conditions.

    ``fields`` may be:
        * List of tags/properties to sort by.
        * Map of ``{<tag/property>: <reversed>}``. If reversed is true, sort the ``tag/property`` in reverse.

    When ``shuffle_mode`` == ``HIGHER_RATING`` or ``RECENT_ADDED``:
        * A ``shuffle_weight`` of 0 will sort the tracks in order according to the desired ``shuffle_mode``.
        * A positive ``shuffle_weight`` shuffles according to the desired ``shuffle_mode``.
          The ``shuffle_weight`` will determine how much randomness is applied to lower ranking items.
        * A negative ``shuffle_weight`` works as above but reverses the final sort order.

    When ``shuffle_mode`` == ``DIFFERENT_ARTIST``:
        * A ``shuffle_weight`` of 1 will group the tracks by artist, shuffling artists randomly.
        * A ``shuffle_weight`` of -1 will shuffle the items randomly.
    """
    sort_fields: Mapping[_SORT_FIELDS_TYPE, bool] = Field(
        description=(
            "Fields to sort by. If defined, this value will always take priority over any shuffle settings "
            "i.e. shuffle settings will be ignored."
        ),
        default_factory=tuple,
        validation_alias="fields",
    )
    shuffle_mode: ShuffleMode | None = Field(
        description="The mode to use for shuffling. Only used when no ``fields`` are given.",
        default=None,
    )
    shuffle_weight: Annotated[float, Field(ge=-1.0, le=1.0)] = Field(
        description=(
            "The weights (between -1 and 1) to apply to certain shuffling modes. "
            "This value will automatically be limited to within the valid range -1 and 1. "
            "Only used when no ``fields`` are given and shuffle_mode is not None or ``RANDOM``."
        ),
        default=0.0,
    )
    ignore_words: set[str] | Sequence[str] = Field(
        description="The words to ignore at the beginning of a string when sorting string values.",
        default={"The", "A"},
    )

    @field_validator("sort_fields", mode="before", check_fields=True)
    @staticmethod
    def _map_fields(fields: str | Iterable[str] | Mapping[str, bool]) -> Mapping[str, bool]:
        if not fields:
            fields = {}
        if isinstance(fields, str):
            fields = (fields,)
        if isinstance(fields, Iterable) and not isinstance(fields, Mapping):
            fields = {field: False for field in fields}
        return fields

    @field_serializer("sort_fields", check_fields=True)
    def _map_fields_values(self, fields: Mapping[str | None, bool]) -> Mapping[str | None, str]:
        return {field: "desc" if rev else "asc" for field, rev in fields.items()}

    @classmethod
    def sort_by_field(
            cls,
            items: MutableSequence[ResourceModel],
            field: _SORT_FIELDS_TYPE | None = None,
            reverse: bool = False,
            ignore_words: Iterable[str] = ()
    ) -> None:
        """
        Sort items by the values of a given field.

        :param items: List of items to sort
        :param field: Tag or property to sort on. If None and reverse is True, reverse the order of the sequence.
        :param reverse: If true, reverse the order of the sort.
        :param ignore_words: The words to ignore at the beginning of a string when sorting string values.
        """
        if field is None:
            if reverse:
                items.reverse()
            return

        sort_key = cls._get_sort_key_by_type(items, field=field, ignore_words=ignore_words)
        items[:] = sorted(items, key=sort_key, reverse=reverse)

    @classmethod
    def _get_sort_key_by_type(
            cls, items: Collection[ResourceModel], field: _SORT_FIELDS_TYPE, ignore_words: Iterable[str]
    ) -> Any:
        try:  # attempt to find an example value to determine the value type for this sort
            value = next(iter(val for item in items if (val := getattr(item, field)) is not None))
        except StopIteration:  # if no example value found, all values are None and so no sort can happen safely. Skip
            raise MusifyValueError(f"No value set for {field} in {items}")

        match value:  # get sort key based on value type
            case str() | HasName():  # key gets name and strips ignore words from string
                def _sort_key(item: ResourceModel) -> tuple[bool, str]:
                    if (val := getattr(item, field)) is not None and isinstance(val, HasName):
                        val = val.name

                    special_start = cls._special_start(val)
                    val = cls._strip_words(val, words=ignore_words).casefold()

                    return not special_start, val.casefold()
            case datetime():  # key converts datetime to floats
                def _sort_key(item: ResourceModel) -> float:
                    field_value = getattr(item, field)
                    return field_value.timestamp() if field_value is not None else 0.0
            case _:
                def _sort_key(item: ResourceModel) -> Any:
                    val = getattr(item, field, None)
                    return val if val else 0

        return _sort_key

    @staticmethod
    def _special_start(value: str) -> bool:
        return re.match(r"^[\W_]", value) is not None

    @staticmethod
    def _strip_words(value: str, words: Iterable[str] | None = (), strip_special_chars: bool = True) -> str:
        """
        Remove the first ignorable word found from the beginning of a string.

        Useful for sorting collections strings with ignorable start words and/or special characters.
        Only removes the first word it finds at the start of the string.
        """
        if not value or not words:
            return value

        if strip_special_chars:
            value = re.sub(r"^\W+", "", value).strip()

        stripped_value = value
        for word in words:
            stripped_value = re.sub(rf"^{word}[\s\W_]", "", value, flags=re.I).strip()
            if stripped_value != value:
                break

        if strip_special_chars:
            stripped_value = re.sub(r"^\W+", "", stripped_value).strip()

        return stripped_value

    @classmethod
    def group_by_field[T: ResourceModel](
            cls,
            items: Collection[T],
            field: _SORT_FIELDS_TYPE,
            ignore_words: Iterable[str] = (),
    ) -> dict[Any, list[T]]:
        """
        Group items by the values of a given field.

        :param items: List of items to sort.
        :param field: Tag or property to group by.
        :param ignore_words: The words to ignore at the beginning of a string when sorting string values.
        :return: Map of grouped items.
        """
        grouped: dict[Any, list[T]] = {}

        def get_value(val: Any) -> Any:
            """Get the value to group by from the given value ``val``"""
            match val:
                case str() | HasName():
                    if isinstance(val, HasName):
                        val = val.name
                    if ignore_words:
                        val = cls._strip_words(val, words=ignore_words, strip_special_chars=False)
                    val = val.casefold()
                case _:
                    pass

            return val

        def group(it: Any, val: Any) -> None:
            """Group items by the given value ``v``"""
            if isinstance(val, list):
                for v in val:
                    group(it=it, val=get_value(v))
                return

            if grouped.get(val) is None:
                grouped[val] = []
            grouped[val].append(it)

        for item in items:
            value = get_value(getattr(item, field))
            group(item, val=value)

        return grouped

    def sort[T: ResourceModel](self, items: MutableSequence[T]) -> None:
        """Sorts a sequence of ``items`` in-place."""
        if len(items) == 0:
            return

        match self.shuffle_mode:
            case _ if self.sort_fields:
                items_nested = self._sort_by_fields(items, fields=iter(self.sort_fields.items()))
                items[:] = self._flatten_groups(items_nested)
            case ShuffleMode.RANDOM:
                shuffle(items)
            case ShuffleMode.HIGHER_RATING:
                self._shuffle_on_rating(items)
            case ShuffleMode.RECENT_ADDED:
                self._shuffle_on_added_at(items)
            case ShuffleMode.DIFFERENT_ARTIST:
                self._shuffle_on_artist(items)

    def _sort_by_fields[T: ResourceModel](
            self,
            groups: MutableSequence[T] | MutableMapping[Any, T],
            fields: Iterator[tuple[_SORT_FIELDS_TYPE, bool]],
    ) -> MutableSequence[T] | MutableMapping[Any, T]:
        """
        Sort items by the given fields recursively in the order given.

        :param groups: Map of items grouped by the last sort value.
        :param fields: Iterator of fields to sort by and whether to reverse the sort for that field.
        :return: Map of grouped and sorted items.
        """
        try:
            field, reverse = next(fields)
        except StopIteration:  # recursive sorting complete
            return groups

        if not isinstance(groups, Mapping):
            groups = {None: groups}

        for key, items in groups.items():  # sort each group and recurse through each field for each group
            self.sort_by_field(items=items, field=field, reverse=reverse, ignore_words=self.ignore_words)
            items_grouped = self.group_by_field(items, field=field, ignore_words=self.ignore_words)
            # noinspection PyTypeChecker
            groups[key] = self._sort_by_fields(items_grouped, fields=copy(fields))

        if set(groups) == {None}:
            groups = {None: groups}

        return groups

    @classmethod
    def _flatten_groups[T: Any](cls, nested: MutableMapping, previous: MutableSequence[T] | None = None) -> list[T]:
        """Flatten the final layers of the values of a nested map to a single list"""
        if previous is None:
            previous = []

        if isinstance(nested, MutableMapping):
            for key, value in nested.items():
                cls._flatten_groups(value, previous=previous)
        elif isinstance(nested, (list, set, tuple)):
            previous.extend(nested)
        else:
            previous.append(nested)

        return previous

    # noinspection PyUnresolvedReferences
    def _shuffle_on_rating(self, items: MutableSequence[HasRating]) -> None:
        if not all(isinstance(item, HasRating) for item in items):
            raise MusifyAttributeError(
                f"The given items cannot be limited on {self.shuffle_mode.name.lower()} "
                "as they do not all have a rating."
            )

        max_value = max(item.rating for item in items)

        def _sort_key(item: HasRating) -> float:
            return self._get_weighted_shuffle_value(item.rating, max_value)

        items[:] = sorted(items, key=_sort_key, reverse=self.shuffle_weight >= 0)

    # noinspection PyUnresolvedReferences
    def _shuffle_on_added_at(self, items: MutableSequence[HasAddedDate]) -> None:
        if not all(isinstance(item, HasAddedDate) for item in items):
            raise MusifyAttributeError(
                f"The given items cannot be limited on {self.shuffle_mode.name.lower()} "
                "as they do not all have an added at date."
            )

        max_value = max(item.added_at.timestamp() for item in items)

        def _sort_key(item: HasAddedDate) -> float:
            return self._get_weighted_shuffle_value(item.added_at.timestamp(), max_value)

        items[:] = sorted(items, key=_sort_key, reverse=self.shuffle_weight >= 0)

    def _get_weighted_shuffle_value(self, value: Number, max_value: Number) -> float:
        weight_factor = uniform(-1, 1) * self.shuffle_weight
        return abs(float(value) - weight_factor * (float(value) - float(max_value)))

    # noinspection PyUnresolvedReferences
    def _shuffle_on_artist(self, items: MutableSequence[HasArtists]) -> None:
        if not all(isinstance(item, HasArtists) for item in items):
            raise MusifyAttributeError(
                f"The given items cannot be limited on {self.shuffle_mode.name.lower()} "
                "as they do not all have an artist."
            )

        shuffle_weight = (self.shuffle_weight + 1) / 2
        artists: list[str] = list({item.artist for item in items})
        shuffle(artists)

        def _sort_key(item: HasArtists) -> int:
            artist = item.artist
            return artists.index(artist) if random() <= shuffle_weight else randrange(0, len(artists))

        shuffle(items)
        items[:] = sorted(items, key=_sort_key)
