from abc import abstractmethod
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Any, Annotated, Self, Union, cast

import mutagen
from mytunes._models.metadata import Attribute
from mytunes.exception import MyTunesTypeError
from pydantic import Field, model_validator, Tag, Discriminator

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
