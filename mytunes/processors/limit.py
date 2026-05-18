"""
Processor that limits the items in a given collection of items
"""
from collections.abc import Collection, MutableSequence
from functools import reduce
from operator import mul
from random import shuffle
from typing import Annotated, final

from pydantic import NonNegativeInt, Field
from pydantic.alias_generators import to_snake

from mytunes._types import LowerSnakeCase
from mytunes.exception import MyTunesTypeError, MyTunesAttributeError
from .._base.enum import IntEnumModel
from .._base.resource import ResourceModel
from mytunes.core.album import HasAlbum
from mytunes.core.properties.file import IsFile
from mytunes.core.properties.length import HasLength
from ._base.dynamic import DynamicProcessor, ProcessorAttribute, processormethod
from mytunes.processors.sort import ItemSorter


class LimitType(IntEnumModel):
    """Represents the possible limit types to apply when filtering a playlist."""
    ITEMS = 0
    ALBUMS = 1

    # units digit is used to determine the scale factor of each unit for time and byte limits
    SECONDS = 11
    MINUTES = 12
    HOURS = 13
    DAYS = 14
    WEEKS = 15

    BYTES = 20
    KILOBYTES = 21
    MEGABYTES = 22
    GIGABYTES = 23
    TERABYTES = 24


@final
class ItemLimiter(DynamicProcessor):
    """Limit items in a Sequence in-place based on given conditions."""
    __final__ = True

    limit_by: NonNegativeInt = Field(
        description="The number of items to limit to. A value of 0 applies no limiting.",
        default=0,
        validation_alias="limit",
    )
    kind: LimitType = Field(
        description="The type to limit on e.g. items, albums, minutes.",
        default=LimitType.ITEMS,
        alias="on",
    )
    sorted_by: Annotated[
        LowerSnakeCase | None,
        ProcessorAttribute(cleaner=lambda x: to_snake(x).replace(" ", "_").strip("_")),
    ] = Field(
        description="Before limiting, sort the collection of items by this function first.",
        default=None,
    )
    allowance: Annotated[float, Field(ge=1.0)] = Field(
        description=(
            "When limiting on bytes or length, add this extra allowance factor to "
            "the max size limit on comparison. e.g. say the limiter currently has 29 minutes worth of songs "
            "in its final list and the max limit is 30 minutes. "
            "The limiter has to now consider whether to include the next song it sees with length 3 minutes. "
            "With an allowance of 0, this song will not be added. However, with an allowance of say 1.33, "
            "it will as the max limit for this comparison becomes 30 * 1.33 = 40. "
            "Now, with 32 minutes worth of songs in the final playlist, "
            "the limit is >30 minutes and the limiter stops processing."
        ),
        default=1,
    )

    def limit[T: ResourceModel](self, items: MutableSequence[T], ignore: Collection[T] = ()) -> None:
        """
        Limit ``items`` in-place based on set conditions.

        :param items: The list of items to limit.
        :param ignore: list of items to ignore when limiting. i.e. keep them in the list regardless.
        """
        if len(items) == 0 or self.limit_by == 0:
            return

        if self.sorted_by:  # sort the input items in-place if sort method given
            self._processor_method(items)

        items_limit = self._get_items_to_limit(items, ignore)
        match self.kind:
            case LimitType.ITEMS:
                items += items_limit[:self.limit_by]
            case LimitType.ALBUMS:
                items += self._limit_on_albums(items_limit)
            case _:
                items += self._limit_on_numeric(items_limit)

    @staticmethod
    def _get_items_to_limit[T](items: MutableSequence[T], ignore: Collection[T] = ()) -> list[T]:
        if ignore:  # filter out the ignore items if given
            items_limit = [item for item in items if item not in ignore]
            items[:] = [item for item in items if item in ignore]
        else:  # make a copy of the given items and clear the original list
            items_limit = [t for t in items]
            items.clear()

        return items_limit

    def _limit_on_albums[T: ResourceModel](self, items: MutableSequence[T]) -> list[T]:
        seen_albums = []
        result = []

        for item in items:
            if not isinstance(item, HasAlbum):
                raise MyTunesAttributeError(
                    "The given item cannot be limited on albums as it does not have an album."
                )
            elif item.album is None:
                continue

            if len(seen_albums) < self.limit_by and item.album not in seen_albums:
                # album limit not yet reached
                seen_albums.append(item.album)
            if item.album in seen_albums:
                result.append(item)

        return result

    def _limit_on_numeric[T: ResourceModel](self, items: MutableSequence[T]) -> list[T]:
        count = 0
        result = []

        for item in items:
            value = self._convert_numeric(item)
            if value is None:
                continue

            count += value
            if count <= self.limit_by * self.allowance:  # limit not yet reached
                result.append(item)
            if count > self.limit_by:  # limit reached
                break

        return result

    def _convert_numeric(self, item: ResourceModel) -> float | None:
        """
        Convert units for item length or size and return the value.

        :raise ItemLimiterError: When the given limit type cannot be found
        """
        match self.kind.value:
            case num if 10 < num < 20:
                if not isinstance(item, HasLength):
                    raise MyTunesAttributeError(
                        "The given item cannot be limited on length as it does not have a length."
                    )
                elif item.length is None:
                    return

                factors = (1, 60, 60, 24, 7)[:num % 10]
                return float(item.length) / reduce(mul, factors, 1)

            case num if 20 <= num < 30:
                if not isinstance(item, IsFile):
                    raise MyTunesAttributeError("The given item cannot be limited on bytes as it is not a file.")
                elif item.size is None:
                    return

                bytes_scale = 1000
                return item.size / (bytes_scale ** (num % 10))

            case _:
                raise MyTunesTypeError(f"Cannot convert to numeric value for this limit type: {self.kind}")

    @processormethod
    def _random(self, items: MutableSequence[ResourceModel]) -> None:
        shuffle(items)

    @processormethod
    def _highest_rating(self, items: MutableSequence[ResourceModel]) -> None:
        ItemSorter.sort_by_field(items, "rating", reverse=True)

    @processormethod
    def _lowest_rating(self, items: MutableSequence[ResourceModel]) -> None:
        ItemSorter.sort_by_field(items, "rating")

    @processormethod
    def _most_recently_played(self, items: MutableSequence[ResourceModel]) -> None:
        ItemSorter.sort_by_field(items, "last_played_at", reverse=True)

    @processormethod
    def _least_recently_played(self, items: list[ResourceModel]) -> None:
        ItemSorter.sort_by_field(items, "last_played_at")

    @processormethod
    def _most_often_played(self, items: list[ResourceModel]) -> None:
        ItemSorter.sort_by_field(items, "play_count", reverse=True)

    @processormethod
    def _least_often_played(self, items: list[ResourceModel]) -> None:
        ItemSorter.sort_by_field(items, "play_count")

    @processormethod
    def _most_recently_added(self, items: list[ResourceModel]) -> None:
        ItemSorter.sort_by_field(items, "added_at", reverse=True)

    @processormethod
    def _least_recently_added(self, items: list[ResourceModel]) -> None:
        ItemSorter.sort_by_field(items, "added_at")
