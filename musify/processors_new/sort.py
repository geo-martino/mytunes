"""
Processor that sorts the given collection of items based on given configuration.
"""
from collections.abc import MutableMapping, Sequence, Iterable, Collection, Iterator
from copy import copy
from datetime import datetime
from random import random, randrange, shuffle, uniform
from typing import Any, Literal, Annotated, Mapping

from aiorequestful.types import Number
from pydantic import Field, field_validator, field_serializer

from musify._types import to_tuple
from musify.local.item.track import LocalTrack
from musify.models import MusifyResource, MusifyEnum
from musify.models.item.album import HasAlbum
from musify.models.item.artist import HasArtists
from musify.models.properties.audio import IsAudioFile
from musify.models.properties.date import HasAddedDate, HasPlayedDate
from musify.models.properties.file import IsFile
from musify.models.properties.length import HasLength
from musify.models.properties.name import HasName
from musify.models.properties.order import HasTrackPosition, HasDiscPosition
from musify.models.properties.rating import HasRating
from musify.processors_new._base import Processor
from musify.processors_new.exception import SorterProcessorError
from musify.utils import flatten_nested, strip_ignore_words, IGNORE_WORDS_DEFAULT

SORT_FIELDS = frozenset({
    *LocalTrack.__tag_fields__,
    *IsFile.__tag_fields__,
    *IsAudioFile.__tag_fields__,
    *HasAddedDate.__tag_fields__,
    *HasPlayedDate.__tag_fields__,
    *HasLength.__tag_fields__,
    *HasName.__tag_fields__,
    *HasTrackPosition.__tag_fields__,
    *HasDiscPosition.__tag_fields__,
    *HasRating.__tag_fields__,
    *HasAlbum.__tag_fields__,
})
_SORT_FIELDS_TYPE = Literal[*SORT_FIELDS]


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
        default=IGNORE_WORDS_DEFAULT,
    )

    @field_validator("sort_fields", mode="before", check_fields=True)
    @staticmethod
    def _map_fields(fields: Any) -> Any:
        if not fields:
            fields = {}
        if isinstance(fields, str):
            fields = (fields,)
        if isinstance(fields, Sequence) and not isinstance(fields, Mapping):
            fields = {field: False for field in fields}
        return fields

    @field_serializer("sort_fields", check_fields=True)
    def _map_fields_values(self, fields: Mapping[str | None, bool]) -> Mapping[str | None, str]:
        return {field: "desc" if rev else "asc" for field, rev in fields.items()}

    @classmethod
    def sort_by_field(
            cls,
            items: list[MusifyResource],
            field: _SORT_FIELDS_TYPE | None = None,
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

        sort_key = cls._get_sort_key_by_type(items, field=field, ignore_words=ignore_words)
        items.sort(key=sort_key, reverse=reverse)

    @staticmethod
    def _get_sort_key_by_type(
            items: Collection[MusifyResource], field: _SORT_FIELDS_TYPE, ignore_words: Iterable[str]
    ) -> Any:
        try:  # attempt to find an example value to determine the value type for this sort
            value = next(iter(val for item in items if (val := getattr(item, field)) is not None))
        except StopIteration:  # if no example value found, all values are None and so no sort can happen safely. Skip
            raise ValueError(f"No value set for {field} in {items}")

        match value:  # get sort key based on value type
            case str():  # key strips ignore words from string
                def _sort_key(item: MusifyResource) -> tuple[bool, bool, str]:
                    not_special_start, not_trimmed, val = strip_ignore_words(getattr(item, field), words=ignore_words)
                    return not_special_start, not_trimmed, val.casefold()
            case datetime():  # key converts datetime to floats
                def _sort_key(item: MusifyResource) -> float:
                    value = getattr(item, field)
                    return value.timestamp() if value is not None else 0.0
            case _:
                def _sort_key(item: MusifyResource) -> float:
                    return getattr(item, field) if hasattr(item, field) else 0

        return _sort_key

    @classmethod
    def group_by_field[T: MusifyResource](
            cls, items: Iterable[T], field: _SORT_FIELDS_TYPE
    ) -> dict[Any, list[T]]:
        """
        Group items by the values of a given field.

        :param items: List of items to sort.
        :param field: Tag or property to group by.
        :return: Map of grouped items.
        """
        def group(v: Any) -> None:
            """Group items by the given value ``v``"""
            if isinstance(v, HasName):
                v = v.name

            if grouped.get(v) is None:
                grouped[v] = []
            grouped[v].append(item)

        grouped: dict[Any, list[T]] = {}
        for item in items:  # produce map of grouped values
            value = to_tuple(getattr(item, field))
            if isinstance(value, Iterable):
                for val in value:
                    group(val)
            else:
                group(value)

        return grouped

    def __call__(self, *args, **kwargs) -> None:
        return self.sort(*args, **kwargs)

    def sort(self, items: list[MusifyResource]) -> None:
        """Sorts a list of ``items`` in-place."""
        if len(items) == 0:
            return

        match self.shuffle_mode:
            case _ if self.sort_fields:
                items_nested = self._sort_by_fields(items, fields=iter(self.sort_fields.items()))
                items.clear()
                items.extend(flatten_nested(items_nested))
            case ShuffleMode.RANDOM:
                shuffle(items)
            case ShuffleMode.HIGHER_RATING:
                self._shuffle_on_rating(items)
            case ShuffleMode.RECENT_ADDED:
                self._shuffle_on_added_at(items)
            case ShuffleMode.DIFFERENT_ARTIST:
                self._shuffle_on_artist(items)

    def _sort_by_fields[T: MusifyResource](
            self,
            groups: list[T] | MutableMapping[Any, T],
            fields: Iterator[tuple[_SORT_FIELDS_TYPE, bool]],
    ) -> list[T] | MutableMapping[Any, T]:
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
            items_grouped = self.group_by_field(items, field=field)
            groups[key] = self._sort_by_fields(items_grouped, fields=copy(fields))

        if set(groups) == {None}:
            groups = {None: groups}

        return groups

    # noinspection PyUnresolvedReferences
    def _shuffle_on_rating(self, items: list[MusifyResource]) -> None:
        if not all(isinstance(item, HasRating) for item in items):
            raise SorterProcessorError(
                f"The given items cannot be limited on {self.shuffle_mode.name.lower()} "
                "as they do not all have a rating."
            )

        max_value = max(item.rating for item in items)

        def _sort_key(item: MusifyResource) -> float:
            return self._get_weighted_shuffle_value(item.rating, max_value)

        items.sort(key=_sort_key, reverse=self.shuffle_weight >= 0)

    # noinspection PyUnresolvedReferences
    def _shuffle_on_added_at(self, items: list[MusifyResource]) -> None:
        if not all(isinstance(item, HasAddedDate) for item in items):
            raise SorterProcessorError(
                f"The given items cannot be limited on {self.shuffle_mode.name.lower()} "
                "as they do not all have an added at date."
            )

        max_value = max(item.added_at.timestamp() for item in items)

        def _sort_key(item: MusifyResource) -> float:
            return self._get_weighted_shuffle_value(item.added_at.timestamp(), max_value)

        items.sort(key=_sort_key, reverse=self.shuffle_weight >= 0)

    def _get_weighted_shuffle_value(self, value: Number, max_value: Number) -> float:
        weight_factor = uniform(-1, 1) * self.shuffle_weight
        return abs(value - weight_factor * (value - max_value))

    # noinspection PyUnresolvedReferences
    def _shuffle_on_artist(self, items: list[MusifyResource]) -> None:
        if not all(isinstance(item, HasArtists) for item in items):
            raise SorterProcessorError(
                f"The given items cannot be limited on {self.shuffle_mode.name.lower()} "
                "as they do not all have an artist."
            )

        shuffle_weight = (self.shuffle_weight + 1) / 2
        artists: list[str] = list({item.artist for item in items})
        shuffle(artists)

        def _sort_key(item: MusifyResource) -> int:
            artist = item.artist
            return artists.index(artist) if random() <= shuffle_weight else randrange(0, len(artists))

        shuffle(items)
        items.sort(key=_sort_key)