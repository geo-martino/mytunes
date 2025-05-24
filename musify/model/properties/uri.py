from __future__ import annotations

from abc import ABCMeta, abstractmethod
from typing import ClassVar, Self

from pydantic import PrivateAttr, model_validator, computed_field, field_validator, Field
from pydantic_core.core_schema import ValidatorFunctionWrapHandler
from yarl import URL

from musify._types import StrippedString
from musify.exception import MusifyValueError
from musify.model import MusifyRootModel
from musify.model._base import _AttributeModel


class URI(MusifyRootModel[str], metaclass=ABCMeta):
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

    # noinspection PyNestedDecorators
    @model_validator(mode="after")
    def _validate_source(self) -> Self:
        if self._source and self.source != self._source:
            raise MusifyValueError(
                f"Given URI does not belong to this {self._source!r} repository type. Found: {self.source!r}"
            )
        return self

    @property
    @abstractmethod
    def source(self) -> str:
        """The remote repository that this URI is from."""
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
        raise NotImplementedError

    @property
    @abstractmethod
    def href(self) -> URL:
        """The URL of the API endpoint for this remote resource."""
        raise NotImplementedError

    # noinspection PyNestedDecorators
    @field_validator("root", mode="wrap", check_fields=True)
    @classmethod
    @abstractmethod
    def from_href[T](cls, value: T, handler: ValidatorFunctionWrapHandler) -> T | Self:
        raise NotImplementedError

    @property
    @abstractmethod
    def url(self) -> URL:
        """The public URL for this remote resource."""
        raise NotImplementedError

    # noinspection PyNestedDecorators
    @field_validator("root", mode="wrap", check_fields=True)
    @classmethod
    @abstractmethod
    def from_url[T](cls, value: T, handler: ValidatorFunctionWrapHandler) -> T | Self:
        raise NotImplementedError

    @property
    def exists(self) -> bool:
        """Whether this URI relates to a resource which actually exists in the remote repository."""
        return self.id != self._unavailable_id

    def __str__(self):
        return self.root

    def __hash__(self):
        return hash(self.root)

    def __eq__(self, other: str | URI):
        if self is other:
            return True
        if isinstance(other, URI):
            return self.root == other.root

        if isinstance(other, URL):
            if self.href == other or self.url == other:
                return True
            other = str(other)

        if isinstance(other, str):
            return str(self) == other or self.id == other

        return super().__eq__(other)


class HasURI[T: URI](_AttributeModel):
    __unique_attributes__ = frozenset({"uri"})
    _uri = PrivateAttr(default=None)

    @computed_field(
        description="The URI for this resource on the remote repository",
    )
    @property
    def uri(self) -> T | None:
        return self._uri

    def __eq__(self, other: HasURI):
        if not isinstance(other, HasURI):
            return super().__eq__(other)
        if self is other:
            return True
        return self.uri is not None and other.uri is not None and self.uri == other.uri


class HasMutableURI(HasURI):
    source: str | None = Field(
        description=(
            "The type of remote repository this resource is associated with. "
            "This is used to extract the appropriate URI from a list of available URIs "
            "and validate incoming URIs contain one URI from the correct source."
        ),
        default=None,
    )
    uris: list[URI] = Field(
        description="A list of URIs that represent this resource.",
        default_factory=list,
    )

    # noinspection PyNestedDecorators
    @field_validator("uris", mode="after", check_fields=True)
    @staticmethod
    def _uris_must_be_from_unique_sources(uris: list[URI]) -> list[URI]:
        sources: set[str] = set()
        duplicates: set[str] = set()

        for uri in uris:
            if uri.source in sources:
                duplicates.add(uri.source)
            sources.add(uri.source)

        if duplicates:
            raise MusifyValueError(f"Duplicate URIs found from sources: {', '.join(duplicates)}")
        return uris

    @property
    def uri(self) -> URI | None:
        if self.source is None:
            return
        return next((uri for uri in self.uris if uri.source == self.source and uri.exists), None)

    @uri.setter
    def uri(self, uri: URI):
        if not isinstance(uri, URI):
            raise MusifyValueError("URI must be a RemoteURI instance")

        if self.source is None:
            self.source = uri.source
        elif uri.source != self.source:
            raise MusifyValueError(f"Cannot set URI from {uri.source} to {self.source}")

        for idx, existing in enumerate(self.uris):  # replace matching source URI in-place at same position
            if existing.source == uri.source:
                self.uris.remove(existing)
                self.uris.insert(idx, uri)
                return

        self.uris.append(uri)

    @uri.deleter
    def uri(self):
        if self.has_uri is None:
            return

        idx = next(i for i, uri in enumerate(self.uris) if uri.source == self.source)
        del self.uris[idx]

    @property
    def has_uri(self) -> bool | None:
        """
        Whether this resource has a URI.

        Returns None if existence is unknown usually because a mapping has not yet been attempted.
        """
        return next((uri.exists for uri in self.uris if uri.source == self.source), None)

    def __eq__(self, other: HasURI):
        if isinstance(other, HasMutableURI) and not other.has_uri:
            return False
        return super().__eq__(other)
