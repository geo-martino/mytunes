from pydantic import Field, ConfigDict
from pydantic.dataclasses import dataclass


@dataclass(config=ConfigDict(frozen=True))
class Attribute:
    """Metadata for a field that is an attribute."""


@dataclass(config=ConfigDict(frozen=True))
class TagAttribute(Attribute):
    """Metadata for a field that corresponds to a tag in a file's metadata."""
    name: str | None = Field(
        description="An alternative name for the tag, if it differs from the field name.",
        default=None,
    )


@dataclass(config=ConfigDict(frozen=True))
class UniqueAttribute(Attribute):
    """Metadata for a field that can identify the uniqueness of a model."""
