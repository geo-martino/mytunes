from __future__ import annotations

from typing import ClassVar, Annotated, Self

from pydantic import Field, field_validator, model_validator, ModelWrapValidatorHandler

from musify.models._base import MusifyModel, AttributeResource


class KeySignature(MusifyModel):
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

    # noinspection PyNestedDecorators
    @model_validator(mode="wrap")
    @classmethod
    def _from_key(cls, value: str, handler: ModelWrapValidatorHandler[Self]) -> Self:
        if not isinstance(value, str):
            return handler(value)

        data = dict(root=cls._extract_root_index_from_key(value), mode=cls._extract_mode_index_from_key(value))
        return handler(data)

    # noinspection PyNestedDecorators
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

    # noinspection PyNestedDecorators
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


class HasKeySignature(AttributeResource):
    """Represents a resource that has a key signature."""
    key: KeySignature | None = Field(
        description="The key signature of this track.",
        default=None,
    )
