import os
from abc import abstractmethod
from collections.abc import Mapping, MutableMapping
from datetime import datetime
from os import sep
from pathlib import Path, PurePath
from typing import Any, Iterable, Annotated, Self, Union

import mutagen
from pydantic import Field, field_validator, model_validator, Tag, ModelWrapValidatorHandler, Discriminator

from musify.exception import MusifyTypeError
from musify.models import abstract_property
from musify.models._attribute import AttributeModelMetaclass
from musify.models._base import BaseModel
from musify.models.exception import MusifyValidationError
from musify.models.metadata import Attribute


class IsFileMetaclass(AttributeModelMetaclass):
    def __new__(mcs, cls_name: str, bases: tuple[type[Any], ...], namespace: dict[str, Any], **kwargs: Any):
        cls = super().__new__(mcs, cls_name, bases, namespace, **kwargs)

        cls.__supported_extensions__ = frozenset({
            *getattr(cls, "__supported_extensions__", []),
            *(attr for base in bases for attr in getattr(base, "__supported_extensions__", []))
        })

        return cls

    @property
    def annotation[T: IsFile](cls: type[T]) -> type[T]:
        # noinspection PyTypeChecker
        classes: set[type[T]] = cls.registered_submodels
        types = (Annotated[kls, Tag(ext)] for kls in classes for ext in kls.__supported_extensions__)
        return Union[*types] if classes else cls

    @property
    def supported_extensions(cls: IsFile) -> set[str]:
        """The file extensions supported by this file type."""
        if cls.__final__:
            return set(cls.__supported_extensions__)
        return {ext for kls in cls.registered_submodels for ext in kls.__supported_extensions__}


# noinspection PyAbstractClass
class IsFile(BaseModel, metaclass=IsFileMetaclass):
    """Attributes and operations for a file on some system."""
    @abstract_property
    def folder(self) -> Annotated[str, Attribute()]:
        """The name of the parent folder of the file."""
        raise NotImplementedError

    @abstract_property
    def filename(self) -> Annotated[str, Attribute()]:
        """The filename without extension."""
        raise NotImplementedError

    @abstract_property
    def ext(self) -> Annotated[str, Attribute()]:
        """The file extension in lowercase."""
        raise NotImplementedError

    @abstract_property
    def size(self) -> Annotated[int | None, Attribute()]:
        """The size of the file in bytes."""
        raise NotImplementedError

    @abstract_property
    def created_at(self) -> Annotated[datetime | None, Attribute()]:
        """The date that the file was created."""
        raise NotImplementedError

    @abstract_property
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


class IsLocalFileMetaclass(IsFileMetaclass):

    @property
    def annotation[T: IsLocalFile](cls: type[T]) -> type[T]:
        if not cls.registered_submodels:
            return cls
        return Annotated[
            super().annotation,
            Field(discriminator=Discriminator(cls._get_ext_from_input)),
        ]


class IsLocalFile(IsFile, metaclass=IsLocalFileMetaclass):
    """Attributes and operations for a file on a local filesystem."""
    path: Annotated[Path, Attribute()] = Field(
        description="The path to the file on the local filesystem."
    )

    # noinspection PyNestedDecorators
    @model_validator(mode="wrap")
    @classmethod
    def _map_path(cls, path: str | Path, handler: ModelWrapValidatorHandler[Self]) -> Self:
        if not isinstance(path, str | Path):
            return handler(path)

        data = dict(path=Path(path))
        return handler(data)

    @model_validator(mode="wrap")
    @classmethod
    def _from_mutagen(cls, file: mutagen.FileType, handler: ModelWrapValidatorHandler[Self]) -> Self:
        if not isinstance(file, mutagen.FileType):
            return handler(file)

        tags = cls._extract_tags_from_mutagen(file)
        return handler(tags)

    @classmethod
    def _extract_tags_from_mutagen(cls, file: mutagen.FileType) -> dict[str, Any]:
        """Extract the tags from a mutagen file object."""
        data = dict(path=file.filename)
        return data

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
                raise MusifyTypeError(f"Cannot discern discriminator value. Unrecognised value type: {type(value)}")

        # noinspection PyUnboundLocalVariable
        return path.suffix.lstrip(".").casefold()

    @property
    def folder(self) -> Annotated[str, Attribute()]:
        return self.path.parent.name

    @property
    def filename(self) -> Annotated[str, Attribute()]:
        return self.path.stem

    @property
    def ext(self) -> Annotated[str, Attribute()]:
        return self.path.suffix.lower()

    @property
    def size(self) -> Annotated[int | None, Attribute()]:
        return self.path.stat().st_size if self.path.is_file() else None

    @property
    def created_at(self) -> Annotated[datetime | None, Attribute()]:
        return datetime.fromtimestamp(self.path.stat().st_ctime) if self.path.is_file() else None

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

        path = str(value.path if isinstance(value, IsLocalFile) else value)
        if not check_existence or os.path.exists(path):
            return path

    def unmap_many(self, values: Iterable[PathInputType], check_existence: bool = False) -> list[str]:
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
            raise MusifyValidationError(f"Unrecognised input type: {value!r}")

        return {path.casefold(): path for path in map(str, value)}

    # noinspection PyNestedDecorators
    @field_validator("stem_map", mode="before", check_fields=True)
    @staticmethod
    def _map_stem_map_from_iterable[T: str | Path](value: Iterable[tuple[T, T]] | Mapping[T, T]) -> dict[str, str]:
        if isinstance(value, Mapping):
            value = value.items()
        elif not isinstance(value, Iterable):
            raise MusifyValidationError(f"Unrecognised input type: {value!r}")

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
