import os
from abc import abstractmethod
from collections.abc import Iterable, Mapping, MutableMapping
from datetime import datetime
from os import sep
from pathlib import Path, PurePath
from typing import Any, Annotated, Self, Union, cast

import mutagen
from pydantic import Field, field_validator, model_validator, Tag, Discriminator

from mytunes._models.exception import MyTunesValidationError
from mytunes._models.metadata import Attribute
from mytunes.exception import MyTunesTypeError
from .._base import BaseModel
from .._base.attribute import AttributeMetaclass


class FileMetaclass(AttributeMetaclass):
    def __new__(mcs, cls_name: str, bases: tuple[type[Any], ...], namespace: dict[str, Any], **kwargs: Any):
        cls = super().__new__(mcs, cls_name, bases, namespace, **kwargs)

        cls.__supported_extensions__ = frozenset({
            *getattr(cls, "__supported_extensions__", []),
            *(attr for base in bases for attr in getattr(base, "__supported_extensions__", []))
        })

        return cls

    @property
    def annotation(cls) -> Self:
        classes = cls.registered_submodels
        types = (Annotated[kls, Tag(ext)] for kls in classes for ext in kls.__supported_extensions__)
        return Union[*types] if classes else cls

    @property
    def supported_extensions(cls) -> set[str]:
        """The file extensions supported by this file type."""
        if cls.__final__:
            return set(cls.__supported_extensions__)
        return {ext for kls in cls.registered_submodels for ext in kls.__supported_extensions__}


# noinspection PyAbstractClass
class IsFile(BaseModel, metaclass=FileMetaclass):
    """Attributes and operations for a file on some system."""
    @property
    @abstractmethod
    def folder(self) -> Annotated[str, Attribute()]:
        """The name of the parent folder of the file."""
        raise NotImplementedError

    @property
    @abstractmethod
    def filename(self) -> Annotated[str, Attribute()]:
        """The filename without extension."""
        raise NotImplementedError

    @property
    @abstractmethod
    def ext(self) -> Annotated[str, Attribute()]:
        """The file extension in lowercase."""
        raise NotImplementedError

    @property
    @abstractmethod
    def size(self) -> Annotated[int | None, Attribute()]:
        """The size of the file in bytes."""
        raise NotImplementedError

    @property
    @abstractmethod
    def modified_at(self) -> Annotated[datetime | None, Attribute()]:
        """The date that the file was last modified."""
        raise NotImplementedError


# noinspection PyAbstractClass
class IsReadableFile(IsFile):
    @abstractmethod
    async def load(self, *args, **kwargs) -> Any:
        """Load the file to this object"""
        raise NotImplementedError


# noinspection PyAbstractClass
class IsWriteableFile(IsFile):
    @abstractmethod
    async def save(self, *args, **kwargs) -> Any:
        """Save this object to file."""
        raise NotImplementedError


class LocalFileMetaclass(FileMetaclass):

    @property
    def annotation(cls) -> Self:
        kls = cast('type[IsLocalFile]', cls)
        if not kls.registered_submodels:
            return kls

        # noinspection PyProtectedMember
        return Annotated[
            super().annotation,
            Field(discriminator=Discriminator(kls._get_ext_from_input)),
        ]


class IsLocalFile(IsFile, metaclass=LocalFileMetaclass):
    """Attributes and operations for a file on a local filesystem."""
    path: Annotated[Path, Attribute()] = Field(
        description="The path to the file on the local filesystem."
    )

    @model_validator(mode="before")
    @classmethod
    def _map_path[T](cls, data: T | str | Path) -> T | dict[str, Any]:
        if not isinstance(data, str | Path):
            return data
        return dict(path=Path(data))

    @model_validator(mode="before")
    @classmethod
    def _from_mutagen[T](cls, data: T | mutagen.FileType) -> T | dict[str, Any]:
        if not isinstance(data, mutagen.FileType):
            return data
        return cls._extract_tags_from_mutagen(data)

    @classmethod
    def _extract_tags_from_mutagen(cls, file: mutagen.FileType) -> dict[str, Any]:
        """Extract the tags from a mutagen file object."""
        return dict(path=file.filename)

    @staticmethod
    def _get_ext_from_input(value: Any) -> str:
        """Get the file extension from the input value."""
        match value:
            case str():
                path = Path(value)
            case Mapping():
                path = Path(value["path"])
            case Path():
                path = value
            case IsLocalFile():
                path = value.path
            case _:
                raise MyTunesTypeError(
                    f"Cannot discern discriminator value. Unrecognised value type: {type(value).__name__!r}"
                )

        return path.suffix.lstrip(".").casefold()

    @property
    def folder(self) -> Annotated[str, Attribute()]:
        return self.path.parent.name

    @property
    def filename(self) -> Annotated[str, Attribute()]:
        return self.path.stem

    @filename.setter
    def filename(self, value: str) -> None:
        if not isinstance(value, str):
            raise MyTunesTypeError("Filename must be a string.")
        if value == self.filename:
            return

        path = self.path.with_stem(value)
        self.path = self.path.rename(path) if self.path.exists() else path

    @property
    def ext(self) -> Annotated[str, Attribute()]:
        return self.path.suffix.lower()

    @property
    def size(self) -> Annotated[int | None, Attribute()]:
        return self.path.stat().st_size if self.path.is_file() else None

    @property
    def modified_at(self) -> Annotated[datetime | None, Attribute()]:
        return datetime.fromtimestamp(self.path.stat().st_mtime) if self.path.is_file() else None


type PathInputType = str | Path | IsLocalFile | None


class PathMapper(BaseModel):
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
