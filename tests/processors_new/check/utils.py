from typing import ClassVar

from musify.models.item.track import Track
from musify.models.properties.name import HasName
from musify.models.properties.uri import HasImmutableURI, HasMutableURI


class HasNameAndImmutableURI(HasName, HasImmutableURI):
    type: ClassVar[str] = Track.type
    name: str


class HasNameAndMutableURI(HasName, HasMutableURI):
    type: ClassVar[str] = Track.type
    name: str
