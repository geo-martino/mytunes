from __future__ import annotations

from abc import abstractmethod
from collections import Counter
from collections.abc import Collection, MutableSet, Iterable
from copy import copy
from functools import total_ordering, cached_property
from typing import ClassVar, Self, Annotated, TYPE_CHECKING, Union, Any

from pydantic import PrivateAttr, computed_field, model_validator, field_validator, Field, TypeAdapter, ConfigDict, \
    validate_call, GetCoreSchemaHandler
from pydantic_core import core_schema
from pydantic_core.core_schema import ValidationInfo, CoreSchema
from yarl import URL

from mytunes._types import StrippedString, TO_SET, HttpURL, to_set
from mytunes.exception import MyTunesTypeError, MyTunesValidationError, MyTunesValueError, MyTunesKeyError
from ..._base import RootModel, make_cls
from ..._base.attribute import AttributeModel, Attribute
from ..._base.resource import ResourceModel, UniqueAttribute
from ...logger import Logger


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
        from ...core._context import RemoteModelContext  # avoid circular import

        # create an unavailable URI is the value is None
        if value is not None or not isinstance(context := info.context, RemoteModelContext) or not context.type:
            return value
        return cls.from_id(cls._unavailable_id, kind=context.type).root

    @model_validator(mode="after")
    def _validate_source(self) -> Self:
        try:
            source = self.source
        except Exception:
            raise MyTunesValidationError(f"No source found.")

        if source.casefold() != self._source.casefold():
            raise MyTunesValidationError(
                f"Given URI is not valid for the {self._source!r} service. Found: {self.source!r}"
            )
        return self

    @property
    def _valid_types(self) -> set[str]:
        return {kls.type for kls in ResourceModel.registered_submodels}

    @model_validator(mode="after")
    def _validate_type(self) -> Self:
        try:
            kind = self.type
        except Exception:
            raise MyTunesValidationError(f"No type found.")

        if kind not in self._valid_types:
            types = Logger.format_list_to_string(sorted(self._valid_types))
            raise MyTunesValidationError(
                f"Given URI is not for an accepted resource type. Accepted types: {types} | Found: {kind!r}"
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
        if cls.__final__:
            raise MyTunesTypeError(
                "Cannot get an adapter for a final model, must be called on a base class with registered submodels"
            )

        # noinspection PyTypeChecker
        classes = {klass for klass in cls.registered_submodels if klass._source.casefold() == source.casefold()}
        if not classes:
            raise MyTunesTypeError(f"No registered {cls.__name__} submodels found for source: {source!r}")

        return TypeAdapter(Union[*classes])

    def __str__(self) -> str:
        return str(self.root)

    def __hash__(self) -> int:
        return hash(self.root)

    def __eq__(self, other: str | URI) -> bool:
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


class UniqueURIs(MutableSet[URI]):
    """Set of URIs with unique sources. All URIs in this set must be of the same type."""
    # noinspection PyUnusedLocal
    @classmethod
    def __get_pydantic_core_schema__(cls, source: Any, handler: GetCoreSchemaHandler) -> CoreSchema:
        values_schema = handler.generate_schema(URI)

        python_schema = core_schema.union_schema(
            [
                core_schema.is_instance_schema(cls),
                values_schema,
                core_schema.set_schema(values_schema),
                core_schema.tuple_variable_schema(values_schema),
                core_schema.list_schema(values_schema),
            ],
        )

        # noinspection PyProtectedMember
        return core_schema.json_or_python_schema(
            json_schema=core_schema.set_schema(values_schema),
            python_schema=core_schema.no_info_plain_validator_function(cls, json_schema_input_schema=python_schema),
        )

    def __init__(self, uris: URI | Iterable[URI] = ()) -> None:
        uris = to_set(uris)

        types = {uri.type for uri in uris}
        if len(types) > 1:
            raise MyTunesValidationError(f"URIs must all be of the same type: {Logger.format_list_to_string(types)}")

        sources = Counter(uri.source for uri in uris)
        duplicate_sources = {source for source, count in sources.items() if count > 1}
        if duplicate_sources:
            raise MyTunesValidationError(
                f"URIs with duplicate sources are not allowed: {Logger.format_list_to_string(duplicate_sources)}"
            )

        self._uris = uris

    @property
    def sources(self) -> set[str]:
        return {uri.source for uri in self}

    @property
    def type(self) -> str | None:
        return next(iter(self)).type if len(self) > 0 else None

    def __str__(self):
        return str(self._uris)

    def __repr__(self):
        return repr(self._uris)

    def __contains__(self, x: URI):
        return x in self._uris

    def __len__(self):
        return len(self._uris)

    def __iter__(self):
        return iter(self._uris)

    @validate_call
    def add(self, value: URI) -> None:
        if self.type is not None and value.type != self.type:
            raise MyTunesTypeError(f"URI type {value.type!r} does not match expected type: {self.type!r}")

        current = self.get(value.source)
        if current is not None:
            raise MyTunesKeyError(f"URI from {value.source!r} already exists in the set")

        self._uris.add(value)

    @validate_call
    def replace(self, value: URI) -> None:
        """
        Add the given URI to the set, replacing any existing URI from the same source.
        If no existing URI with a matching source exists, the URI will be just simply be added to the set.
        """
        current = self.get(value.source)
        if current is not None:
            self._uris.remove(current)

        self.add(value)

    @validate_call
    def discard(self, value: URI):
        self._uris.discard(value)

    @validate_call
    def get(self, source: str) -> URI | None:
        """Get the URI with the specified source."""
        return next((uri for uri in self if uri.source.casefold() == source.casefold()), None)

    @validate_call
    def drop(self, source: str) -> None:
        """Drop the URI with the specified source."""
        current = self.get(source)
        if current is not None:
            self._uris.remove(current)


# noinspection PyAbstractClass
class HasURI(AttributeModel, ResourceModel, metaclass=make_cls()):
    # not sure how to define this in a way that works for both without causing issues with pydantic...
    # this is either a field or property in child classes so have put this for type checking only for now
    if TYPE_CHECKING:
        uri: URI | None

    def __new__(cls, *args, **kwargs):
        # check for presence of uri field or property in child class
        fields = cls.model_fields.keys() | cls.model_computed_fields.keys()
        fields |= {name for name in dir(cls) if isinstance(getattr(cls, name), property)}
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

    def __eq__(self, other: HasURI) -> bool:
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
    uris: UniqueURIs = Field(
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
        if self.source is None and len(self.uris.sources) == 1:
            self.__dict__["source"] = next(iter(self.uris.sources))
        return self

    @field_validator("uris", mode="after", check_fields=True)
    @classmethod
    def _validate_uris_match_type(cls, uris: UniqueURIs) -> UniqueURIs:
        if uris.type is not None and uris.type != cls.type:
            raise MyTunesValidationError(f"URI type {uris.type!r} does not match expected type {cls.type!r}")
        return uris

    @computed_field(
        description="The URI of the currently configured source.",
    )
    @property
    def uri(self) -> Annotated[URI | None, UniqueAttribute()]:
        if self.source is None:
            return None

        uri = self.uris.get(self.source)
        return uri if uri is not None and uri.exists else None

    @uri.setter
    def uri(self, value: URI | None):
        if value is None:
            if self.source is None:
                return None

            from .._context import RemoteModelContext  # avoid circular import
            context = RemoteModelContext(type=self.type)

            # mark unavailable
            value = URI.get_adapter_for_source(self.source).validate_python(None, context=context)

        if not isinstance(value, URI):
            raise MyTunesTypeError("URI must be a URI instance")

        if self.source is not None and value.source.casefold() != self.source.casefold():
            raise MyTunesTypeError(f"Cannot set URI from {value.source!r} to {self.source!r}")
        if value.type != self.type:
            raise MyTunesTypeError(f"Cannot set URI of type {value.type!r} for type {self.type!r}")

        self.uris.replace(value)
        if self.source is None:
            self.source = value.source

        if hasattr(self, "unique_keys"):
            del self.unique_keys  # clear the cached property

    @uri.deleter
    def uri(self):
        if self.has_uri is None:
            return

        uri = self.uris.get(self.source)
        self.uris.remove(uri)

        if hasattr(self, "unique_keys"):
            del self.unique_keys  # clear the cached property

    @property
    def has_uri(self) -> bool | None:
        if self.source is None:
            return None

        uri = self.uris.get(self.source)
        return uri.exists if uri is not None else None
