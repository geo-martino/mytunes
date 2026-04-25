import functools
import os
import sys
from abc import abstractmethod
from collections.abc import Iterable, Mapping, MutableMapping
from contextlib import suppress
from os import sep
from pathlib import Path, PurePath, PureWindowsPath, PurePosixPath
from typing import final, Any, Annotated

from pydantic import Field, field_validator, ValidationError

from mytunes._types import TO_SET
from mytunes.core.properties.file import IsLocalFile
from mytunes.exception import MyTunesValidationError, MyTunesError
from ..._base import BaseModel

type PathInputType = str | Path | IsLocalFile | None


# noinspection PyAbstractClass
class PathMapper(BaseModel):
    """
    Simple path mapper which extracts paths from :py:class:`File` objects.
    Can be extended by child classes for more complex mapping operations.
    """
    @abstractmethod
    def serialise(self, value: PathInputType, check_existence: bool = False) -> str | None:
        """Serialise the given value according to the current mapping."""
        raise NotImplementedError

    def serialise_many(self, values: Iterable[PathInputType], check_existence: bool = False) -> list[str]:
        """Run :py:meth:`map` operation on many ``values`` only returning those values that are not None or empty."""
        paths = [self.serialise(value=value, check_existence=check_existence) for value in values]
        return list(filter(None, paths))

    def serialise_many_to_paths(self, values: Iterable[PathInputType], check_existence: bool = False) -> list[Path]:
        """Run :py:meth:`map` operation on many ``values`` only returning those values that are not None or empty."""
        return list(map(Path, self.serialise_many(values, check_existence=check_existence)))

    @abstractmethod
    def deserialise(self, value: PathInputType, check_existence: bool = False) -> str | None:
        """Deserialise the given value according to the current mapping."""
        raise NotImplementedError

    def deserialise_many(self, values: Iterable[PathInputType], check_existence: bool = False) -> list[str]:
        """Run :py:meth:`unmap` operation on many ``values`` only returning those values that are not None or empty."""
        paths = [self.deserialise(value=value, check_existence=check_existence) for value in values]
        return list(filter(None, paths))

    def deserialise_many_to_paths(self, values: Iterable[PathInputType], check_existence: bool = False) -> list[Path]:
        """Run :py:meth:`unmap` operation on many ``values`` only returning those values that are not None or empty."""
        return list(map(Path, self.deserialise_many(values, check_existence=check_existence)))


@final
class PathModelMapper(PathMapper):
    __final__ = True

    def serialise(self, value: PathInputType, check_existence: bool = False) -> str | None:
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

    @functools.wraps(serialise)
    def deserialise(self, *args, **kwargs) -> str | None:
        return self.serialise(*args, **kwargs)


@final
class PathParentMapper(PathMapper):
    """
    A more complex path mapper which attempts to replace the parents of paths from strings and :py:class:`File` objects.
    Plus, attempts to case-correct paths.

    Useful for cross-platform support. Can be used to correct paths if the same file exists in
    different locations according to different mounts and/or multiple operating parents.
    """
    __final__ = True

    parent_serialise: Mapping[str, str] = Field(
        description="A map of ``{<parent to be replaced>: <its replacement>}`` to be applied during serialization.",
        default_factory=dict,
        alias="serialise",
    )
    parent_deserialise: Mapping[str, str] = Field(
        description="A map of ``{<parent to be replaced>: <its replacement>}`` to be applied during deserialization.",
        default_factory=dict,
        alias="deserialise",
    )

    @field_validator("parent_serialise", "parent_deserialise", mode="before", check_fields=True)
    @staticmethod
    def _map_parents_from_iterable[T: str | Path](value: Iterable[tuple[T, T]] | Mapping[T, T]) -> dict[str, str]:
        if isinstance(value, Mapping):
            value = value.items()
        elif not isinstance(value, Iterable):
            raise MyTunesValidationError(f"Unrecognised input type: {value!r}")

        return {str(k): str(v) for k, v in value}

    def serialise(self, value: PathInputType, check_existence: bool = False) -> str | None:
        """
        Map the given value by replacing its parent according to stored ``parent_serialise``,
        correcting path separators according to the separators of the replacement parent.

        :param value: The value to map.
        :param check_existence: When True, check the path exists before returning it. If it doesn't exist, returns None.
        :return: The path if ``check_existence`` is False, or if ``check_existence`` is True and path exists,
            None otherwise.
        """
        if not value:
            return

        path = str(value.path if isinstance(value, IsLocalFile) else value)

        seps = ()
        for parent, replacement in self.parent_serialise.items():
            if path.casefold().startswith(parent.casefold()):
                if "/" in replacement and "/" not in path:
                    seps = ("\\", "/")
                elif "\\" in replacement and "\\" not in path:
                    seps = ("/", "\\")
                path = sep.join([replacement.rstrip("\\/"), path[len(parent):].lstrip("\\/")]).rstrip("\\/")
                break

        if sep == "\\":
            path = path.replace("\\\\", "\\")
        if seps:
            path = path.replace(*seps)

        if not check_existence or os.path.exists(path):
            return path

    def deserialise(self, value: PathInputType, check_existence: bool = False) -> str | None:
        """
        Map the given value by replacing its parent according to stored ``parent_deserialise``,
        correcting path separators according to the separators of the replacement parent.

        :param value: The value to map.
        :param check_existence: When True, check the path exists before returning it. If it doesn't exist, returns None.
        :return: The path if ``check_existence`` is False, or if ``check_existence`` is True and path exists,
            None otherwise.
        """
        if not value:
            return

        path = str(value.path if isinstance(value, IsLocalFile) else value)

        seps = ()
        for parent, replacement in self.parent_deserialise.items():
            if path.casefold().startswith(parent.casefold()):
                if "/" in replacement and "/" not in path:
                    seps = ("\\", "/")
                elif "\\" in replacement and "\\" not in path:
                    seps = ("/", "\\")
                path = sep.join([replacement.rstrip("\\/"), path[len(parent):].lstrip("\\/")])
                break

        if sep == "\\":
            path = path.replace("\\\\", "\\")
        if seps:
            path = path.replace(*seps)

        if not check_existence or os.path.exists(path):
            return path


class SystemPath(BaseModel):
    windows: PureWindowsPath | None = Field(
        description="The directory to use for Windows systems.",
        validation_alias="win",
        default=None,
    )
    mac: PurePosixPath | None = Field(
        description="The directory to use for Mac systems.",
        default=None,
    )
    linux: PurePosixPath | None = Field(
        description="The directory to use for Linux systems.",
        validation_alias="lin",
        default=None,
    )

    @property
    def path(self) -> Path | None:
        """The path for the current system."""
        match sys.platform:
            case "win32":
                return Path(self.windows) if self.windows is not None else None
            case "darwin":
                return Path(self.mac) if self.mac is not None else None
            case "linux":
                return Path(self.linux) if self.linux is not None else None
            case platform:
                raise MyTunesError(f"Unrecognised current platform: {platform!r}.")

    @property
    def others(self) -> set[PurePath]:
        """The paths for other systems."""
        # noinspection PyTypeChecker
        return {path for path in self.model_dump().values() if path is not None and path != self.path}

    def __str__(self):
        return str(self.path)

    @classmethod
    def get_current_system_path[T](cls, data: T | Mapping[str, Any]) -> T | Path:
        """Validate and extract the current system path from the given data."""
        if not isinstance(data, Mapping) and not isinstance(data, cls):
            return data

        with suppress(ValidationError):
            return cls.model_validate(data).path
        return data


class SystemPaths(BaseModel):
    windows: Annotated[set[PureWindowsPath], TO_SET] | None = Field(
        description="The directories to use for Windows systems.",
        validation_alias="win",
        default=None,
    )
    mac: Annotated[set[PurePosixPath], TO_SET] | None = Field(
        description="The directories to use for Mac systems.",
        default=None,
    )
    linux: Annotated[set[PurePosixPath], TO_SET] | None = Field(
        description="The directories to use for Linux systems.",
        validation_alias="lin",
        default=None,
    )

    @property
    def paths(self) -> set[Path] | None:
        """The path for the current system."""
        match sys.platform:
            case "win32":
                return set(map(Path, self.windows)) if self.windows is not None else None
            case "darwin":
                return set(map(Path, self.mac)) if self.mac is not None else None
            case "linux":
                return set(map(Path, self.linux)) if self.linux is not None else None
            case platform:
                raise MyTunesError(f"Unrecognised current platform: {platform!r}.")

    @property
    def others(self) -> set[PurePath]:
        """The paths for other systems."""
        # noinspection PyTypeChecker
        return {
            path for paths in self.model_dump().values()
            for path in paths if path is not None and path not in self.paths
        }

    @classmethod
    def get_current_system_paths[T](cls, data: T | Mapping[str, Any]) -> T | set[Path]:
        """Validate and extract the current system paths from the given data."""
        if not isinstance(data, Mapping) and not isinstance(data, cls):
            return data

        with suppress(ValidationError):
            return cls.model_validate(data).paths
        return data
