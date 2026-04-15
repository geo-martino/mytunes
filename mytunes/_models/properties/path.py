import os
from collections.abc import Iterable, Mapping, MutableMapping
from os import sep
from pathlib import Path, PurePath
from typing import final

from mytunes._models import BaseModel
from mytunes.exception import MyTunesValidationError
from mytunes._models.properties.file import IsLocalFile
from pydantic import Field, field_validator

type PathInputType = str | Path | IsLocalFile | None


@final
class PathMapper(BaseModel):
    """
    Simple path mapper which extracts paths from :py:class:`File` objects.
    Can be extended by child classes for more complex mapping operations.
    """
    __final__ = True

    def map(self, value: PathInputType, check_existence: bool = False) -> str | None:
        """
        Map the given ``value`` by either extracting the path from a :py:class:`File` object,
        or returning the ``value`` as is, assuming it is a string.

        :param value: The value to extract a path from.
        :param check_existence: When True, check the path exists before returning it. If it doesn't exist, returns None.
        :return: The path if ``check_existence`` is False, or if ``check_existence`` is True and path exists,
            None otherwise.
        """
        if not value:
            return

        path = str(value.path if isinstance(value, IsLocalFile) else value)
        if not check_existence or os.path.exists(path):
            return path

    def map_many(self, values: Iterable[PathInputType], check_existence: bool = False) -> list[str]:
        """Run :py:meth:`map` operation on many ``values`` only returning those values that are not None or empty."""
        paths = [self.map(value=value, check_existence=check_existence) for value in values]
        return list(filter(None, paths))

    def map_many_to_paths(self, values: Iterable[PathInputType], check_existence: bool = False) -> list[Path]:
        """Run :py:meth:`map` operation on many ``values`` only returning those values that are not None or empty."""
        return list(map(Path, self.map_many(values, check_existence=check_existence)))

    def unmap(self, value: PathInputType, check_existence: bool = False) -> str | None:
        """
        Map the given ``value`` by either extracting the path from a :py:class:`File` object,
        or returning the ``value`` as is, assuming it is a string.

        :param value: The value to extract a path from.
        :param check_existence: When True, check the path exists before returning it. If it doesn't exist, returns None.
        :return: The path if ``check_existence`` is False, or if ``check_existence`` is True and path exists,
            None otherwise.
        """
        if not value:
            return

        path = str(value.path if isinstance(value, IsLocalFile) else value)
        if not check_existence or os.path.exists(path):
            return path

    def unmap_many(self, values: Iterable[PathInputType], check_existence: bool = False) -> list[str]:
        """Run :py:meth:`unmap` operation on many ``values`` only returning those values that are not None or empty."""
        paths = [self.unmap(value=value, check_existence=check_existence) for value in values]
        return list(filter(None, paths))

    def unmap_many_to_paths(self, values: Iterable[PathInputType], check_existence: bool = False) -> list[Path]:
        """Run :py:meth:`unmap` operation on many ``values`` only returning those values that are not None or empty."""
        return list(map(Path, self.unmap_many(values, check_existence=check_existence)))


# noinspection PyFinal
@final
class PathStemMapper(PathMapper):
    """
    A more complex path mapper which attempts to replace the stems of paths from strings and :py:class:`File` objects.
    Plus, attempts to case-correct paths.

    Useful for cross-platform support. Can be used to correct paths if the same file exists in
    different locations according to different mounts and/or multiple operating systems.
    """
    __final__ = True

    available_paths: MutableMapping[str, str] = Field(
        description=
        """
        A map of the available paths stored in this object. Simply ``{<lower-case path>: <correctly-cased path>}``.
        When assigning new values to this property, the stored map will update itself
        with the new values rather than overwrite.
        """,
        default_factory=dict,
    )
    stem_map: MutableMapping[str, str] = Field(
        description=
        """
        A map of ``{<stem to be replaced>: <its replacement>}``.
        Assigning new values to this property updates itself
        plus the ``stem_unmap`` property with the reverse of this map.
        """,
        default_factory=dict,
    )

    @property
    def stem_map_reversed(self) -> dict[str, str]:
        """
        A map of ``{<replacement stems>: <stem to be replaced>}`` i.e. just the opposite map of ``stem_map``.
        Assign new values to ``stem_map`` to update.
        """
        return dict(list(item[::-1]) for item in self.stem_map.items())

    @field_validator("available_paths", mode="before", check_fields=True)
    @staticmethod
    def _map_available_paths_from_iterable(value: Iterable[str | PurePath]) -> dict[str, str]:
        if isinstance(value, str | PurePath):
            value = [value]
        elif not isinstance(value, Iterable):
            raise MyTunesValidationError(f"Unrecognised input type: {value!r}")

        return {path.casefold(): path for path in map(str, value)}

    @field_validator("stem_map", mode="before", check_fields=True)
    @staticmethod
    def _map_stem_map_from_iterable[T: str | Path](value: Iterable[tuple[T, T]] | Mapping[T, T]) -> dict[str, str]:
        if isinstance(value, Mapping):
            value = value.items()
        elif not isinstance(value, Iterable):
            raise MyTunesValidationError(f"Unrecognised input type: {value!r}")

        return {str(k): str(v) for k, v in value}

    def map(self, value: PathInputType, check_existence: bool = False) -> str | None:
        """
        Map the given value by replacing its stem according to stored ``stem_map``,
        correcting path separators according to the separators of the replacement stem,
        and case correcting path from stored ``available_paths``.

        :param value: The value to map.
        :param check_existence: When True, check the path exists before returning it. If it doesn't exist, returns None.
        :return: The path if ``check_existence`` is False, or if ``check_existence`` is True and path exists,
            None otherwise.
        """
        if not value:
            return

        path = str(value.path if isinstance(value, IsLocalFile) else value)

        seps = ()
        for stem, replacement in self.stem_map.items():
            if path.casefold().startswith(stem.casefold()):
                if "/" in replacement and "/" not in path:
                    seps = ("\\", "/")
                elif "\\" in replacement and "\\" not in path:
                    seps = ("/", "\\")
                path = sep.join([replacement.rstrip("\\/"), path[len(stem):].lstrip("\\/")]).rstrip("\\/")
                break

        if sep == "\\":
            path = path.replace("\\\\", "\\")
        if seps:
            path = path.replace(*seps)

        path = self.available_paths.get(path.casefold(), path)
        if not check_existence or os.path.exists(path):
            return path

    def unmap(self, value: PathInputType, check_existence: bool = False) -> str | None:
        """
        Map the given value by replacing its stem according to stored ``stem_unmap``,
        correcting path separators according to the separators of the replacement stem,
        and case correcting path from stored ``available_paths`` (i.e. mostly the reverse of :py:meth:`map`).

        :param value: The value to map.
        :param check_existence: When True, check the path exists before returning it. If it doesn't exist, returns None.
        :return: The path if ``check_existence`` is False, or if ``check_existence`` is True and path exists,
            None otherwise.
        """
        if not value:
            return

        path = str(value.path if isinstance(value, IsLocalFile) else value)

        seps = ()
        for stem, replacement in self.stem_map_reversed.items():
            if path.casefold().startswith(stem.casefold()):
                if "/" in replacement and "/" not in path:
                    seps = ("\\", "/")
                elif "\\" in replacement and "\\" not in path:
                    seps = ("/", "\\")
                path = sep.join([replacement.rstrip("\\/"), path[len(stem):].lstrip("\\/")])
                break

        if sep == "\\":
            path = path.replace("\\\\", "\\")
        if seps:
            path = path.replace(*seps)

        path = self.available_paths.get(path.casefold(), path)
        if not check_existence or os.path.exists(path):
            return path
