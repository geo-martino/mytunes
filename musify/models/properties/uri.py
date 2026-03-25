from __future__ import annotations

from abc import abstractmethod
from collections.abc import Collection
from functools import total_ordering
from typing import ClassVar, Self, Any, Annotated, TypeIs

from pydantic import PrivateAttr, computed_field, model_validator, field_validator, Field, BeforeValidator
from pydantic_core.core_schema import ValidatorFunctionWrapHandler
from yarl import URL

from musify._types import StrippedString, to_list
from musify.models import abstract_property, ResourceModel
from musify.models._attribute import AttributeModel
from musify.models._base import RootModel
from musify.models._metaclass import makecls
from musify.models.exception import MusifyValidationError
from musify.models.metadata import UniqueAttribute, Attribute
from musify.models.url import HttpURL


# noinspection PyAbstractClass
@total_ordering
class URI(RootModel[str]):
    """Stores a URI for a resource from a specific remote repository."""
    _source: ClassVar[str] = PrivateAttr(
        # description=(
        #     "The remote repository that the URI is from. "
        #     "This is used to validate incoming URI values belong to this repository."
        # ),
    )
    _unavailable_id: ClassVar[StrippedString] = PrivateAttr(
        # description=(
        #     "A special ID that indicates this URI does not exist in the remote repository. "
        #     "This is used to indicate that the URI is not available."
        # ),
        default="unavailable",
    )

    def __new__(cls, *args, **kwargs):
        if cls is URI:
            raise MusifyValidationError(
                f"{cls.__name__} cannot be instantiated directly, must be subclassed with a specific source and type"
            )
        return super().__new__(cls)

    # noinspection PyNestedDecorators
    @model_validator(mode="after")
    def _validate_source(self) -> Self:
        if not isinstance(self.root, str):
            raise MusifyValidationError(f"URI root must be a string, got {type(self.root)}")

        if self.source != self._source:
            raise MusifyValidationError(
                f"Given URI does not belong to this {self._source!r} repository type. Found: {self.source!r}"
            )
        return self

    @abstract_property
    def source(self) -> str:
        """The remote repository that this URI is from."""
        raise NotImplementedError

    @abstract_property
    def type(self) -> str:
        """The type of resource this URI represents."""
        raise NotImplementedError

    @abstract_property
    def id(self) -> str:
        """The unique identifier for this URI."""
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def from_id[T](cls, value: T, kind: str) -> T | Self:
        """Construct a URI from an ID value and resource type."""
        raise NotImplementedError

    @abstract_property
    def api_url(self) -> HttpURL:
        """The URL of the API endpoint for this remote resource."""
        raise NotImplementedError

    # noinspection PyNestedDecorators
    @field_validator("root", mode="wrap", check_fields=True)
    @classmethod
    @abstractmethod
    def from_api_url(cls, value: Any, handler: ValidatorFunctionWrapHandler) -> Self:
        """Construct a URI from an API endpoint URL."""
        pass

    @abstract_property
    def public_url(self) -> HttpURL:
        """The public URL for this remote resource."""
        raise NotImplementedError

    # noinspection PyNestedDecorators
    @field_validator("root", mode="wrap", check_fields=True)
    @classmethod
    @abstractmethod
    def from_public_url(cls, value: Any, handler: ValidatorFunctionWrapHandler) -> Self:
        """Construct a URI from a public URL."""
        pass

    @property
    def exists(self) -> bool:
        """Whether this URI relates to a resource which actually exists in the remote repository."""
        return self.id != self._unavailable_id

    def __str__(self) -> str:
        return str(self.root)

    def __hash__(self):
        return hash(self.root)

    def __eq__(self, other: str | URI):
        if self is other:
            return True
        if isinstance(other, URI):
            return self.root == other.root

        if isinstance(other, URL):
            if self.api_url == other or self.public_url == other:
                return True
            other = str(other)

        if isinstance(other, str):
            return str(self) == other or self.id == other

        return super().__eq__(other)

    def __lt__(self, other: URI):
        return str(self) < str(other)


class HasImmutableURI[UT: URI](AttributeModel, ResourceModel, metaclass=makecls()):
    uri: Annotated[URI | None, UniqueAttribute()] = Field(
        description="The URI for this resource on the remote repository",
        frozen=True,
        default=None,
    )

    @field_validator("uri", mode="after", check_fields=True)
    @classmethod
    def _validate_uri_matches_type(cls, uri: UT | None) -> UT | None:
        if uri is None or not isinstance(uri, URI):
            return uri

        if not uri.type == cls.type:
            raise MusifyValidationError(f"URI type {uri.type!r} does not match expected type {cls.type!r}")
        return uri

    def __eq__(self, other: HasURI):
        if not isinstance(other, (HasImmutableURI, HasMutableURI)) or (self.uri is None and other.uri is None):
            return super().__eq__(other)
        if self is other:
            return True
        return self.uri is not None and other.uri is not None and self.uri == other.uri


class HasMutableURI(AttributeModel, ResourceModel, metaclass=makecls()):
    source: Annotated[str | None, Attribute()] = Field(
        description=(
            "The type of remote repository this resource is associated with. "
            "This is used to extract the appropriate URI from a list of available URIs "
            "and validate incoming URIs contain one URI from the correct source."
        ),
        default=None,
    )
    uris: Annotated[list[URI], BeforeValidator(to_list)] = Field(
        description="A list of URIs that represent this resource.",
        default_factory=list,
    )

    def __init__(self, **data):
        # support passing a single URI for convenience
        uri = data.pop("uri", None)
        uris = data.pop("uris", [])
        if uri is not None:
            uris.append(uri)

        super().__init__(uris=uris, **data)

    @model_validator(mode="after")
    def _set_source_from_uri(self) -> Self:
        if self.source is None and len(set(uri.source for uri in self.uris)) == 1:
            # noinspection PyTypeChecker
            self.source = self.uris[0].source
        return self

    # noinspection PyNestedDecorators
    @field_validator("uris", mode="after", check_fields=True)
    @staticmethod
    def _validate_uris_from_unique_sources[T: Collection](uris: T) -> T:
        sources: set[str] = set()
        duplicates: set[str] = set()

        for uri in uris:
            if uri.source in sources:
                duplicates.add(uri.source)
            sources.add(uri.source)

        if duplicates:
            raise MusifyValidationError(f"Duplicate URIs found from sources: {', '.join(duplicates)}")
        return uris

    # noinspection PyNestedDecorators
    @field_validator("uris", mode="after", check_fields=True)
    @classmethod
    def _validate_uris_match_type[T: Collection](cls, uris: T) -> T:
        for uri in uris:
            if not uri.type == cls.type:
                raise MusifyValidationError(f"URI type {uri.type!r} does not match expected type {cls.type!r}")
        return uris

    @computed_field(
        description="The URI of the currently configured source.",
    )
    @property
    def uri(self) -> Annotated[URI | None, UniqueAttribute()]:
        if self.source is None:
            return
        return next((uri for uri in self.uris if uri.source == self.source and uri.exists), None)

    @uri.setter
    def uri(self, value: URI):
        if not isinstance(value, URI):
            raise MusifyValidationError("URI must be a URI instance")

        if self.source is None:
            self.source = value.source
        elif value.source != self.source:
            raise MusifyValidationError(f"Cannot set URI from {value.source} to {self.source}")

        for idx, existing in enumerate(self.uris):  # replace matching source URI in-place at same position
            if existing.source == value.source:
                self.uris.remove(existing)
                self.uris.insert(idx, value)
                return

        self.uris.append(value)
        if hasattr(self, "unique_keys"):
            del self.unique_keys  # clear the cached property

    @uri.deleter
    def uri(self):
        if self.has_uri is None:
            return

        idx = next(i for i, uri in enumerate(self.uris) if uri.source == self.source)
        del self.uris[idx]
        if hasattr(self, "unique_keys"):
            del self.unique_keys  # clear the cached property

    @property
    def has_uri(self) -> bool | None:
        """
        Whether this resource has a URI.

        Returns None if existence is unknown usually because a mapping has not yet been attempted.
        """
        return next((uri.exists for uri in self.uris if uri.source == self.source), None)

    def __eq__(self, other: HasURI):
        if not isinstance(other, (HasImmutableURI, HasMutableURI)) or (self.uri is None and other.uri is None):
            return False
        if self is other:
            return True
        return self.uri is not None and other.uri is not None and self.uri == other.uri


type HasURI[UT] = HasImmutableURI[UT] | HasMutableURI


def item_has_uri(item: Any) -> TypeIs[HasURI]:
    """Whether the given item has a URI."""
    return any((
        isinstance(item, HasMutableURI) and item.has_uri,
        isinstance(item, HasImmutableURI) and item.uri is not None,
    ))
