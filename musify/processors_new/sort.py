"""
Processor that sorts the given collection of items based on given configuration.
"""
import random
from collections.abc import Callable, Mapping, MutableMapping, Sequence, Iterable
from copy import copy
from datetime import datetime
from random import shuffle
from typing import Any, Literal, Annotated

from aiorequestful.types import UnitIterable, Number
from pydantic import Field, field_validator, field_serializer

from musify.local.item.track import LocalTrack
from musify.models import MusifyResource
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
from musify.types import MusifyEnum
from musify.utils import flatten_nested, strip_ignore_words, to_collection, IGNORE_WORDS_DEFAULT

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

    sort_fields: Mapping[_SORT_FIELDS_TYPE | None, bool] = Field(
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

        tag_name = field.map(field)[0].name.lower()

        # attempt to find an example value to determine the value type for this sort
        example_value = None
        for item in items:
            example_value = getattr(item, tag_name)
            if example_value is not None:
                break
        if example_value is None:
            # if no example value found, all values are None and so no sort can happen safely. Skip
            return

        # get sort key based on value type
        if isinstance(example_value, datetime):  # key converts datetime to floats
            def sort_key(it: MusifyResource) -> float:
                """Get the sort key for timestamp tags from the given ``it``"""
                value = it[tag_name]
                return value.timestamp() if value is not None else 0.0
        elif isinstance(example_value, str):  # key strips ignore words from string
            def sort_key(it: MusifyResource) -> tuple[bool, str]:
                """Get the sort key for string tags from the given ``it``"""
                not_special_start, value = strip_ignore_words(it[tag_name], words=ignore_words)
                return not_special_start, value.casefold()
        else:
            sort_key: Callable[[MusifyResource], object] = \
                lambda t: getattr(item, tag_name) if hasattr(item, tag_name) else 0

        items.sort(key=sort_key, reverse=reverse)

    @classmethod
    def group_by_field[T: MusifyResource](
            cls, items: UnitIterable[T], field: _SORT_FIELDS_TYPE | None = None
    ) -> dict[Any, list[T]]:
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
            value = to_collection(getattr(item, tag_name))
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

        if self.sort_fields:
            items_nested = self._sort_by_fields(
                {None: items}, fields=dict(self.sort_fields), ignore_words=self.ignore_words
            )
            items.clear()
            items.extend(flatten_nested(items_nested))
        elif self.shuffle_mode == ShuffleMode.RANDOM:
            shuffle(items)
        elif self.shuffle_mode == ShuffleMode.HIGHER_RATING:
            self._shuffle_on_rating(items)
        elif self.shuffle_mode == ShuffleMode.RECENT_ADDED:
            self._shuffle_on_added_at(items)
        elif self.shuffle_mode == ShuffleMode.DIFFERENT_ARTIST:
            self._shuffle_on_artist(items)

    def _get_weighted_shuffle_value(self, value: Number, max_value: Number) -> float:
        weight_factor = random.uniform(-1, 1) * self.shuffle_weight
        return abs(value - weight_factor * (value - max_value))

    # noinspection PyUnresolvedReferences
    def _shuffle_on_rating(self, items: list[MusifyResource]) -> None:
        if not all(isinstance(item, HasRating) for item in items):
            raise SorterProcessorError(
                f"The given items cannot be limited on {self.shuffle_mode.name.lower()} "
                "as they do not all have a rating."
            )

        max_value: float = max(item.rating for item in items)
        items.sort(
            key=lambda item: self._get_weighted_shuffle_value(item.rating, max_value),
            reverse=self.shuffle_weight >= 0
        )

    # noinspection PyUnresolvedReferences
    def _shuffle_on_added_at(self, items: list[MusifyResource]) -> None:
        if not all(isinstance(item, HasAddedDate) for item in items):
            raise SorterProcessorError(
                f"The given items cannot be limited on {self.shuffle_mode.name.lower()} "
                "as they do not all have an added at date."
            )

        max_value: float = max(item.added_at.timestamp() for item in items)
        items.sort(
            key=lambda item: self._get_weighted_shuffle_value(item.added_at.timestamp(), max_value),
            reverse=self.shuffle_weight >= 0
        )

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

        def sort_key(artist: str) -> int:
            """Get sort key for a given ``artist``"""
            return artists.index(artist) if random.random() <= shuffle_weight else random.randrange(0, len(artists))

        shuffle(items)
        items.sort(key=lambda item: sort_key(item.artist))

    @classmethod
    def _sort_by_fields(
            cls,
            items_grouped: MutableMapping,
            fields: MutableMapping[_SORT_FIELDS_TYPE | None, bool],
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
