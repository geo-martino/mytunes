from __future__ import annotations

from abc import abstractmethod
from collections.abc import Collection
from copy import copy
from functools import total_ordering, cached_property
from typing import ClassVar, Self, Annotated, TYPE_CHECKING, cast, Union

from pydantic import PrivateAttr, computed_field, model_validator, field_validator, Field, TypeAdapter, ConfigDict
from pydantic_core.core_schema import ValidationInfo
from yarl import URL

from .._base import BaseModel, RootModel, makecls
from .._base.attribute import AttributeModel, Attribute
from .._base.resource import ResourceModel, UniqueAttribute
from mytunes._types import StrippedString, TO_SET, HttpURL
from mytunes.exception import MyTunesTypeError, MyTunesValidationError


# noinspection PyAbstractClass
@total_ordering
class URI(RootModel[str]):
    """Stores a URI for a resource from a specific remote service."""
    model_config = ConfigDict(frozen=True)

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

    @model_validator(mode="before")
    @classmethod
    def _validate_unavailable[T](cls, value: T, info: ValidationInfo) -> T | str:
        from ..core._context import RemoteModelContext  # avoid circular import

        # create an unavailable URI is the value is None
        if value is not None or not isinstance(context := info.context, RemoteModelContext) or not context.type:
            return value
        return cls.from_id(cls._unavailable_id, kind=context.type).root

    @model_validator(mode="after")
    def _validate_source(self) -> Self:
        if not isinstance(self.root, str):
            raise MyTunesValidationError(f"URI root must be a string, got {type(self.root).__name__!r}")

        if self.source.casefold() != self._source.casefold():
            raise MyTunesValidationError(
                f"Given URI is not valid for the {self._source!r} service. Found: {self.source!r}"
            )
        return self

    @property
    @abstractmethod
    def source(self) -> str:
        """The remote service that this URI is from."""
        raise NotImplementedError

    @property
    @abstractmethod
    def type(self) -> str:
        """The type of resource this URI represents."""
        raise NotImplementedError

    @property
    @abstractmethod
    def id(self) -> str:
        """The unique identifier for this URI."""
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def from_id[T](cls, value: T, kind: str) -> T | Self:
        """Construct a URI from an ID value and resource type."""
        raise NotImplementedError

    @property
    @abstractmethod
    def api_url(self) -> HttpURL:
        """The URL of the API endpoint for this remote resource."""
        raise NotImplementedError

    @field_validator("root", mode="before", check_fields=True)
    @classmethod
    @abstractmethod
    def from_api_url[T](cls, value: T) -> T | str:
        """Construct a URI from an API endpoint URL."""
        pass

    @property
    @abstractmethod
    def public_url(self) -> HttpURL:
        """The public URL for this remote resource."""
        raise NotImplementedError

    @field_validator("root", mode="before", check_fields=True)
    @classmethod
    @abstractmethod
    def from_public_url[T](cls, value: T) -> T | str:
        """Construct a URI from a public URL."""
        pass

    @property
    def exists(self) -> bool:
        """Whether this URI relates to a resource which actually exists in the remote service."""
        return self.id != self._unavailable_id

    @classmethod
    def get_adapter_for_source(cls, source: str) -> TypeAdapter[URI]:
        """Generate a type adapter for the registered URI submodels of a given source."""
        kls = cast('type[BaseModel]', cls)
        if kls.__final__:
            raise MyTunesTypeError(
                "Cannot get an adapter for a final model, must be called on a base class with registered submodels"
            )

        # noinspection PyTypeChecker
        classes = [klass for klass in kls.registered_submodels if klass._source.casefold() == source.casefold()]
        if not classes:
            raise MyTunesTypeError(f"No registered {cls.__name__} submodels found for source: {source!r}")

        return TypeAdapter(Union[*classes])

    def __str__(self) -> str:
        return str(self.root)

    def __hash__(self) -> int:
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


# noinspection PyAbstractClass
class HasURI(AttributeModel, ResourceModel, metaclass=makecls()):
    # not sure how to define this in a way that works for both without causing issues with pydantic...
    # this is either a field or property in child classes so have put this for type checking only for now
    if TYPE_CHECKING:
        uri: URI | None

    def __new__(cls, *args, **kwargs):
        # check for presence of uri field or property in child class
        fields = cls.model_fields.keys() | cls.model_computed_fields.keys()
        fields |= {name for name, method in cls.__dict__.items() if isinstance(method, property)}
        if "uri" not in fields:
            raise MyTunesValidationError(f"{cls.__name__} must have a 'uri' field or property to be instantiated")

        return super().__new__(cls)

    @property
    @abstractmethod
    def has_uri(self) -> bool | None:
        """
        Whether this resource has a valid URI.

        Returns None if existence is unknown usually because a mapping has not yet been attempted.
        """
        raise NotImplementedError

    def __eq__(self, other: HasURI):
        if not isinstance(other, HasURI) or (self.uri is None and other.uri is None):
            return False
        if self is other:
            return True
        return self.uri is not None and other.uri is not None and self.uri == other.uri


class HasImmutableURI[UT: URI](HasURI):
    uri: Annotated[URI, UniqueAttribute()] = Field(
        description="The URI for this resource on the remote service",
        frozen=True,
        default=None,
    )

    @field_validator("uri", mode="after", check_fields=True)
    @classmethod
    def _validate_uri_matches_type(cls, uri: UT | None) -> UT | None:
        if uri is None or not isinstance(uri, URI):
            return uri

        if not uri.type == cls.type:
            raise MyTunesValidationError(f"URI type {uri.type!r} does not match expected type {cls.type!r}")
        return uri

    @computed_field(
        description="Whether this resource has a valid URI.",
        return_type=bool,
        repr=False,
    )
    @cached_property
    def has_uri(self) -> bool:
        return self.uri is not None and self.uri.exists


class HasMutableURI(HasURI):
    source: Annotated[str | None, Attribute()] = Field(
        description=(
            "The type of remote service this resource is associated with. "
            "This is used to extract the appropriate URI from a list of available URIs "
            "and validate incoming URIs contain one URI from the correct source."
        ),
        default=None,
    )
    uris: Annotated[set[URI], TO_SET] = Field(
        description="A set of URIs that represent this resource.",
        default_factory=set,
        validation_alias="uri",
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
        if self.source is None and len(set(source := uri.source for uri in self.uris)) == 1:
            self.__dict__["source"] = source.casefold()
        return self

    @field_validator("uris", mode="after", check_fields=True)
    @staticmethod
    def _validate_uris_from_unique_sources[T: Collection](uris: T) -> T:
        sources: set[str] = set()
        duplicates: set[str] = set()

        for uri in uris:
            source = uri.source.casefold()
            if source in sources:
                duplicates.add(source)
            sources.add(source)

        if duplicates:
            raise MyTunesValidationError(f"Duplicate URIs found from sources: {', '.join(duplicates)}")
        return uris

    @field_validator("uris", mode="after", check_fields=True)
    @classmethod
    def _validate_uris_match_type[T: Collection](cls, uris: T) -> T:
        for uri in uris:
            if not uri.type == cls.type:
                raise MyTunesValidationError(f"URI type {uri.type!r} does not match expected type {cls.type!r}")
        return uris

    @computed_field(
        description="The URI of the currently configured source.",
    )
    @property
    def uri(self) -> Annotated[URI | None, UniqueAttribute()]:
        if self.source is None:
            return
        return next((uri for uri in self.uris if uri.source.casefold() == self.source.casefold() and uri.exists), None)

    @uri.setter
    def uri(self, value: URI | None):
        if not isinstance(value, URI):
            raise MyTunesValidationError("URI must be a URI instance")

        if self.source is None:
            self.source = value.source.casefold()
        elif value.source.casefold() != self.source.casefold():
            raise MyTunesValidationError(f"Cannot set URI from {value.source} to {self.source}")

        for existing in copy(self.uris):
            if existing.source.casefold() == value.source.casefold():
                self.uris.remove(existing)

        self.uris.add(value)
        if hasattr(self, "unique_keys"):
            del self.unique_keys  # clear the cached property

    @uri.deleter
    def uri(self):
        if self.has_uri is None:
            return

        uri = self.uri
        if uri is None:
            uri = next(uri for uri in self.uris if uri.source.casefold() == self.source.casefold())

        self.uris.remove(uri)
        if hasattr(self, "unique_keys"):
            del self.unique_keys  # clear the cached property

    @property
    def has_uri(self) -> bool | None:
        return next((uri.exists for uri in self.uris if uri.source == self.source), None)
