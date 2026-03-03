## DEPRECATED

"""
All core type hints to use throughout the entire package.
"""
from collections.abc import Iterable
from enum import IntEnum
from typing import Self, Any

from musify.exception import MusifyEnumError


class MusifyEnum(IntEnum):
    """Generic class for :py:class:`IntEnum` implementations for the entire package."""

    @staticmethod
    def _unique_list(value: Iterable[Any]) -> list[Any]:
        """
        Returns a copy of the given ``value`` that contains only unique elements.
        Useful for producing unique lists whilst preserving order.
        """
        unique = []
        for item in value:
            if item not in unique:
                unique.append(item)
        return unique

    @classmethod
    def map(cls, enum: Self) -> list[Self]:
        """
        Optional mapper to apply to the enum found during :py:meth:`all`, :py:meth:`from_name`,
        and :py:meth:`from_value` calls
        """
        return [enum]

    @classmethod
    def all(cls) -> list[Self]:
        """Get all enums for this enum."""
        return cls._unique_list(e for enum in cls if enum.name != "ALL" for e in cls.map(enum))

    @classmethod
    def from_name(cls, *names: str, fail_on_many: bool = True) -> list[Self]:
        """
        Returns all enums that match the given enum names

        :param fail_on_many: If more than one enum is found, raise an exception.
        :raise EnumNotFoundError: If a corresponding enum cannot be found.
        """
        names_upper = [name.strip().upper() for name in names]
        enums = cls._unique_list(e for enum in cls if enum.name in names_upper for e in cls.map(enum))

        if len(enums) == 0:
            raise MusifyEnumError(names)
        elif len(enums) > 1 and fail_on_many:
            raise MusifyEnumError(value=enums, message="Too many enums found")

        return enums

    @classmethod
    def from_value(cls, *values: int, fail_on_many: bool = True) -> list[Self]:
        """
        Returns all enums that match the given enum values

        :param fail_on_many: If more than one enum is found, raise an exception.
        :raise EnumNotFoundError: If a corresponding enum cannot be found.
        """
        enums = cls._unique_list(e for enum in cls if enum.value in values for e in cls.map(enum))
        if len(enums) == 0:
            raise MusifyEnumError(values)
        elif len(enums) > 1 and fail_on_many:
            raise MusifyEnumError(value=enums, message="Too many enums found")
        return enums
