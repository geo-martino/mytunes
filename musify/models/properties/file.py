import os
from abc import ABCMeta, abstractmethod
from collections.abc import Mapping, MutableMapping
from datetime import datetime
from os import sep
from pathlib import Path, PurePath
from typing import Any, Collection, Iterable, ClassVar

import mutagen
from pydantic import Field, AliasChoices, field_validator, PositiveInt, model_validator

from musify.exception import MusifyValueError
from musify.models._base import _AttributeModel, MusifyModel


class _IsFile(_AttributeModel):
    path: Path = Field(
        description="The path to the file"
    )
    format: str = Field(
        description="The format (or file type) of the file.",
        validation_alias=AliasChoices("ext", "extension"),
        default=None,
        exclude=True,
    )

    # noinspection PyNestedDecorators
    @model_validator(mode="before")
    @classmethod
    def extract_tags_from_mutagen[F](cls, file: F) -> F | dict[str, Any]:
        """Extract the tags from a mutagen file object, if applicable."""
        if not isinstance(file, mutagen.FileType):
            return file

        return dict(path=file.filename, format=Path(file.filename).suffix.lstrip("."))

    # noinspection PyNestedDecorators
    @model_validator(mode="before")
    @staticmethod
    def _extract_format_from_path[T](value: T) -> T | dict[str, Any]:
        if not isinstance(value, dict) or "format" in value or (path := value.get("path")) is None:
            return value
        return value | {"format": PurePath(str(path)).suffix.lstrip(".")}

    @property
    def folder(self) -> str:
        """The name of the parent folder of the file."""
        return self.path.parent.name

    @property
    def filename(self) -> str:
        """The filename without extension."""
        return self.path.stem

    @property
    def ext(self) -> str:
        """The file extension in lowercase."""
        return self.path.suffix.lower()

    @property
    def size(self) -> PositiveInt | None:
        """The size of the file in bytes."""
        return self.path.stat().st_size if self.path.is_file() else None

    @property
    def created_at(self) -> datetime | None:
        """The date that the file was created."""
        return datetime.fromtimestamp(self.path.stat().st_ctime) if self.path.is_file() else None

    @property
    def modified_at(self) -> datetime | None:
        """The date that the file was last modified."""
        return datetime.fromtimestamp(self.path.stat().st_mtime) if self.path.is_file() else None

    @classmethod
    def get_filepaths(cls, folder: str | Path) -> set[Path]:
        """Get all files in a given folder that match this File object's valid filetypes recursively."""
        paths: set[Path] = set()
        folder = Path(folder)

        for ext in cls.valid_extensions:
            paths |= set(folder.rglob(str(Path("**", f"[!.]*{ext}"))))
            # paths |= set(folder.rglob(str(Path("**", f".*{ext}"))))

        # do not return paths in the recycle bin in Windows-based folders
        return {path for path in paths if "$RECYCLE.BIN" not in path.parts}


class IsFile(_IsFile, metaclass=ABCMeta):
    """Attributes and operations for a file on a filesystem."""
    __tag_fields__ = frozenset({
        *_IsFile.model_fields,
        *{name for name, method in vars(_IsFile).items() if isinstance(method, property)}
    })

    @abstractmethod
    async def load(self, *args, **kwargs) -> Any:
        """Load the file to this object"""
        raise NotImplementedError

    @abstractmethod
    async def save(self, *args, **kwargs) -> Any:
        """Save this object to file."""
        raise NotImplementedError


type PathInputType = str | Path | _IsFile | None


class PathMapper(MusifyModel):
    """
    Simple path mapper which extracts paths from :py:class:`File` objects.
    Can be extended by child classes for more complex mapping operations.
    """

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

        path = str(value.path if isinstance(value, _IsFile) else value)
        if not check_existence or os.path.exists(path):
            return path

    def map_many(self, values: Collection[PathInputType], check_existence: bool = False) -> list[str]:
        """Run :py:meth:`map` operation on many ``values`` only returning those values that are not None or empty."""
        paths = [self.map(value=value, check_existence=check_existence) for value in values]
        return [path for path in paths if path]

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

        path = str(value.path if isinstance(value, _IsFile) else value)
        if not check_existence or os.path.exists(path):
            return path

    def unmap_many(self, values: Collection[PathInputType], check_existence: bool = False) -> list[str]:
        """Run :py:meth:`unmap` operation on many ``values`` only returning those values that are not None or empty."""
        paths = [self.unmap(value=value, check_existence=check_existence) for value in values]
        return [path for path in paths if path]


class PathStemMapper(PathMapper):
    """
    A more complex path mapper which attempts to replace the stems of paths from strings and :py:class:`File` objects.
    Plus, attempts to case-correct paths.

    Useful for cross-platform support. Can be used to correct paths if the same file exists in
    different locations according to different mounts and/or multiple operating systems.
    """
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

    # noinspection PyNestedDecorators
    @field_validator("available_paths", mode="before", check_fields=True)
    @staticmethod
    def _map_available_paths_from_iterable(value: Iterable[str | PurePath]) -> dict[str, str]:
        if isinstance(value, str | PurePath):
            value = [value]
        elif not isinstance(value, Iterable):
            raise MusifyValueError(f"Unrecognised input type: {value!r}")

        return {path.casefold(): path for path in map(str, value)}

    # noinspection PyNestedDecorators
    @field_validator("stem_map", mode="before", check_fields=True)
    @staticmethod
    def _map_stem_map_from_iterable(
            value: Iterable[tuple[str | PurePath, str | PurePath]] | Mapping[str | PurePath, str | PurePath]
    ) -> dict[str, str]:
        if isinstance(value, Mapping):
            value = value.items()
        elif not isinstance(value, Iterable):
            raise MusifyValueError(f"Unrecognised input type: {value!r}")

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

        path = str(value.path if isinstance(value, _IsFile) else value)

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

        path = str(value.path if isinstance(value, _IsFile) else value)

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
