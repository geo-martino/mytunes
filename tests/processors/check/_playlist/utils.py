from functools import total_ordering
from typing import ClassVar

from mytunes.core._item.track import Track
from mytunes.core.properties.name import HasName
from mytunes.core.properties.uri import HasImmutableURI, HasMutableURI


@total_ordering
class HasNameAndImmutableURI(HasName, HasImmutableURI):
    type: ClassVar[str] = Track.type
    name: str

    def __eq__(self, other: object) -> bool:  # make equality check on just names work
        if not isinstance(other, HasNameAndImmutableURI) and not (isinstance(other, HasNameAndMutableURI)):
            return super().__eq__(other)
        return self.uri == other.uri or self.name == other.name

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, HasNameAndImmutableURI) and not (isinstance(other, HasNameAndMutableURI)):
            return super().__lt__(other)
        return self.name < other.name


@total_ordering
class HasNameAndMutableURI(HasName, HasMutableURI):
    type: ClassVar[str] = Track.type
    name: str

    def __eq__(self, other: object) -> bool:  # make equality check on just names work
        if not isinstance(other, HasNameAndImmutableURI) and not (isinstance(other, HasNameAndMutableURI)):
            return super().__eq__(other)
        return self.uri == other.uri or self.name == other.name

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, HasNameAndImmutableURI) and not (isinstance(other, HasNameAndMutableURI)):
            return super().__lt__(other)
        return self.name < other.name
