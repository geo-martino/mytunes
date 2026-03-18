from dataclasses import dataclass, field


@dataclass(frozen=True)
class Attribute:
    """Metadata for a field that is an attribute."""


@dataclass(frozen=True)
class TagAttribute(Attribute):
    """Metadata for a field that corresponds to a tag in a file's metadata."""
    name: str | None = field(
        doc="An alternative name for the tag, if it differs from the field name.",
        default=None,
    )


@dataclass(frozen=True)
class UniqueAttribute(Attribute):
    """Metadata for a field that can identify the uniqueness of a model."""
