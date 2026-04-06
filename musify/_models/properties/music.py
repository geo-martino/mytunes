from __future__ import annotations

from typing import ClassVar, Annotated, Any

from pydantic import Field, field_validator, model_validator

from musify._models.metadata import Attribute
from .._base import BaseModel
from .._base.attribute import AttributeModel


class KeySignature(BaseModel):
    """Represents a key signature."""
    _root_notes: ClassVar[tuple[str, ...]] = (
        "C", "C#/Db", "D", "D#/Eb", "E", "F", "F#/Gb", "G", "G#/Ab", "A", "A#/Bb", "B"
    )

    root: Annotated[int, Field(ge=0, le=11)] = Field(
        description="An index representing the root note of the key of this track.",
    )
    mode: Annotated[int, Field(ge=0, le=1)] = Field(
        description="The mode of this track.",
    )

    @model_validator(mode="before")
    @classmethod
    def _from_key[T](cls, data: T | str) -> T | dict[str, Any]:
        if not isinstance(data, str):
            return data

        return dict(
            root=cls._extract_root_index_from_key(data),
            mode=cls._extract_mode_index_from_key(data)
        )

    @field_validator("root", mode="before", check_fields=True)
    @classmethod
    def _extract_root_index_from_key[T: str](cls, value: T) -> T | int:
        if not isinstance(value, str):
            return value

        value_split = tuple(v.rstrip("m") for v in value.split("/"))
        try:
            root_notes = [note.split("/")[0] for note in cls._root_notes]
            return root_notes.index(value_split[0])
        except ValueError:
            root_notes = [note.split("/")[-1] for note in cls._root_notes]
            return root_notes.index(value_split[-1])

    @field_validator("mode", mode="before", check_fields=True)
    @staticmethod
    def _extract_mode_index_from_key[T: str](value: T) -> T | int:
        if not isinstance(value, str):
            return value
        return int(value.endswith("m"))

    @property
    def key(self) -> str:
        """A string representation of the key in alphabetical musical notation format."""
        key_base = self._root_notes[self.root].split("/")
        if self.mode:
            key_base = (v + "m" for v in key_base)
        return "/".join(key_base)

    # noinspection PyTypeChecker
    @key.setter
    def key(self, value: str) -> None:
        self.root = value
        self.mode = value

    def __str__(self) -> str:
        return str(self.key)

    def __hash__(self) -> int:
        return hash((self.root, self.mode))


class HasKeySignature(AttributeModel):
    """Represents a resource that has a key signature."""
    key: Annotated[KeySignature | None, Attribute()] = Field(
        description="The key signature of this track.",
        default=None,
    )
