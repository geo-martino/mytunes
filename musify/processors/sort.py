"""
Processor that sorts the given collection of items based on given configuration.
"""
import random
from collections.abc import Callable, Mapping, MutableMapping, Sequence, Iterable
from copy import copy
from datetime import datetime
from random import shuffle
from typing import Any

from aiorequestful.types import UnitSequence, UnitIterable, Number

from musify.base import MusifyItem
from musify.field import Field
from musify.processors.base import Processor
from musify.processors.exception import SorterProcessorError
from musify.types import MusifyEnum
from musify.utils import flatten_nested, strip_ignore_words, to_collection, limit_value, IGNORE_WORDS_DEFAULT


class ShuffleMode(MusifyEnum):
    """Represents the possible shuffle modes to use when shuffling items using :py:class:`ItemSorter`."""
    RANDOM = 0
    HIGHER_RATING = 1
    RECENT_ADDED = 2
    DIFFERENT_ARTIST = 3


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

    :param fields: Fields to sort by. If defined, this value will always take priority over any shuffle settings
        i.e. shuffle settings will be ignored.
    :param shuffle_mode: The mode to use for shuffling. Only used when no ``fields`` are given.
        WARNING: Currently only ``RANDOM`` shuffle mode has been implemented.
        Any other given value will default to ``RANDOM`` shuffling.
    :param shuffle_weight: The weights (between -1 and 1) to apply to certain shuffling modes.
        This value will automatically be limited to within the valid range -1 and 1.
        Only used when no ``fields`` are given and shuffle_mode is not None or ``RANDOM``.
    :param ignore_words: The words to ignore at the beginning of a string when sorting string values.
    """

    __slots__ = ("sort_fields", "shuffle_mode", "shuffle_weight", "ignore_words")

    @classmethod
    def sort_by_field(
            cls,
            items: list[MusifyItem],
            field: Field | None = None,
            reverse: bool = False,
            ignore_words: Iterable[str] = IGNORE_WORDS_DEFAULT
    ) -> None:
        """
        Sort items by the values of a given field.

        :param items: List of items to sort
        :param field: Tag or property to sort on. If None and reverse is True, reverse the order of the list.
        :param reverse: If true, reverse the order of the sort.
        :param ignore_words: The words to ignore at the beginning of a string when sorting string values.
        """
        if field is None:
            if reverse:
                items.reverse()
            return

        tag_name = field.map(field)[0].name.lower()

        # attempt to find an example value to determine the value type for this sort
        example_value = None
        for item in items:
            example_value = item[tag_name]
            if example_value is not None:
                break
        if example_value is None:
            # if no example value found, all values are None and so no sort can happen safely. Skip
            return

        # get sort key based on value type
        if isinstance(example_value, datetime):  # key converts datetime to floats
            def sort_key(it: MusifyItem) -> float:
                """Get the sort key for timestamp tags from the given ``it``"""
                value = it[tag_name]
                return value.timestamp() if value is not None else 0.0
        elif isinstance(example_value, str):  # key strips ignore words from string
            def sort_key(it: MusifyItem) -> tuple[bool, str]:
                """Get the sort key for string tags from the given ``it``"""
                not_special_start, value = strip_ignore_words(it[tag_name], words=ignore_words)
                return not_special_start, value.casefold()
        else:
            sort_key: Callable[[MusifyItem], object] = lambda t: t[tag_name] if t[tag_name] else 0

        items.sort(key=sort_key, reverse=reverse)

    @classmethod
    def group_by_field[T: MusifyItem](cls, items: UnitIterable[T], field: Field | None = None) -> dict[Any, list[T]]:
        """
        Group items by the values of a given field.

        :param items: List of items to sort.
        :param field: Tag or property to group by. None returns map of ``{None: <items>}``.
        :return: Map of grouped items.
        """
        if field is None:  # group by None
            return {None: to_collection(items, list)}

        tag_name = field.map(field)[0].name.lower()

        def group(v: Any) -> None:
            """Group items by the given value ``v``"""
            if grouped.get(v) is None:
                grouped[v] = []
            grouped[v].append(item)

        grouped: dict[Any | None, list[T]] = {}
        for item in items:  # produce map of grouped values
            value = to_collection(item[tag_name])
            if isinstance(value, Iterable):
                for val in value:
                    group(val)
            else:
                group(value)

        return grouped

    def __init__(
            self,
            fields: UnitSequence[Field | None] | Mapping[Field | None, bool] = (),
            shuffle_mode: ShuffleMode | None = None,
            shuffle_weight: float = 0.0,
            ignore_words: Iterable[str] = IGNORE_WORDS_DEFAULT
    ):
        fields = to_collection(fields, list) if isinstance(fields, Field) else fields
        self.sort_fields: dict[Field | None, bool] = {field: False for field in fields} \
            if isinstance(fields, Sequence) else fields

        self.shuffle_mode = shuffle_mode
        self.shuffle_weight = limit_value(shuffle_weight, floor=-1, ceil=1)
        self.ignore_words = ignore_words

    def __call__(self, *args, **kwargs) -> None:
        return self.sort(*args, **kwargs)

    def sort(self, items: list[MusifyItem]) -> None:
        """Sorts a list of ``items`` in-place."""
        if len(items) == 0:
            return

        if self.sort_fields:
            items_nested = self._sort_by_fields(
                {None: items}, fields=self.sort_fields, ignore_words=self.ignore_words
            )
            items.clear()
            items.extend(flatten_nested(items_nested))
        elif self.shuffle_mode == ShuffleMode.RANDOM:
            shuffle(items)
        elif self.shuffle_mode == ShuffleMode.HIGHER_RATING:
            self._shuffle_on_rating(items)
        elif self.shuffle_mode == ShuffleMode.RECENT_ADDED:
            self._shuffle_on_date_added(items)
        elif self.shuffle_mode == ShuffleMode.DIFFERENT_ARTIST:
            self._shuffle_on_artist(items)

    def _get_weighted_shuffle_value(self, value: Number, max_value: Number) -> float:
        weight_factor = random.uniform(-1, 1) * self.shuffle_weight
        return abs(value - weight_factor * (value - max_value))

    # noinspection PyUnresolvedReferences
    def _shuffle_on_rating(self, items: list[MusifyItem]) -> None:
        if not all(hasattr(item, "rating") for item in items):
            raise SorterProcessorError(
                "Cannot shuffle sort on rating as the given items do not all have a 'rating' property"
            )

        max_value: float = max(item.rating for item in items)
        items.sort(
            key=lambda item: self._get_weighted_shuffle_value(item.rating, max_value),
            reverse=self.shuffle_weight >= 0
        )

    # noinspection PyUnresolvedReferences
    def _shuffle_on_date_added(self, items: list[MusifyItem]) -> None:
        if not all(hasattr(item, "date_added") for item in items):
            raise SorterProcessorError(
                "Cannot shuffle sort on date added as the given items do not all have a 'date_added' property"
            )

        max_value: float = max(item.date_added.timestamp() for item in items)
        items.sort(
            key=lambda item: self._get_weighted_shuffle_value(item.date_added.timestamp(), max_value),
            reverse=self.shuffle_weight >= 0
        )

    # noinspection PyUnresolvedReferences
    def _shuffle_on_artist(self, items: list[MusifyItem]) -> None:
        if not all(hasattr(item, "artist") for item in items):
            raise SorterProcessorError(
                "Cannot shuffle sort on artist as the given items do not all have an 'artist' property"
            )

        shuffle_weight = (self.shuffle_weight + 1) / 2
        artists: list[str] = list({item.artist for item in items})
        shuffle(artists)

        def sort_key(artist: str) -> int:
            """Get sort key for a given ``artist``"""
            return artists.index(artist) if random.random() <= shuffle_weight else random.randrange(0, len(artists))

        shuffle(items)
        items.sort(key=lambda item: sort_key(item.artist))

    @classmethod
    def _sort_by_fields(
            cls,
            items_grouped: MutableMapping, fields: MutableMapping[Field | None, bool],
            ignore_words: Iterable[str] = IGNORE_WORDS_DEFAULT
    ) -> MutableMapping:
        """
        Sort items by the given fields recursively in the order given.

        :param items_grouped: Map of items grouped by the last sort value.
        :param ignore_words: The words to ignore at the beginning of a string when sorting string values.
        :return: Map of grouped and sorted items.
        """
        field, reverse = next(iter(fields.items()), (None, None))
        if field is None:  # sorting complete
            return items_grouped

        fields = copy(fields)
        fields.pop(field)

        # sort each group and recurse through each field for each group
        for i, (key, items) in enumerate(items_grouped.items(), 1):
            cls.sort_by_field(items=items, field=field, reverse=reverse, ignore_words=ignore_words)
            groups = cls.group_by_field(items, field=field)
            items_grouped[key] = cls._sort_by_fields(groups, fields=fields, ignore_words=ignore_words)

        return items_grouped

    def as_dict(self):
        fields = None
        if isinstance(self.sort_fields, Mapping):
            fields = {field.name.lower(): "desc" if r else "asc" for field, r in self.sort_fields.items()}

        return {
            "sort_fields": fields,
            "shuffle_mode": self.shuffle_mode,
            "shuffle_weight": self.shuffle_weight
        }
