import functools
from abc import abstractmethod
from collections.abc import Mapping, Callable
from contextlib import suppress
from typing import Self, Any, Annotated

from aiorequestful.auth import Authoriser
from aiorequestful.cache.backend import ResponseCache
from aiorequestful.cache.exception import CacheError
from aiorequestful.cache.session import CachedSession
from aiorequestful.request import RequestHandler
from aiorequestful.response.payload import JSONPayloadHandler
from pydantic import model_validator, InstanceOf, Field, ValidationError, ConfigDict

from mytunes._types import get_generic
from mytunes.core.api._endpoints import HasEndpoints, Endpoints, _map_handler
from mytunes.core.remote import RemoteModel
from mytunes.exception import EndpointsError
from mytunes.core.properties.logger import HasLogger
from mytunes.core.properties.uri import URI
from .._context import RemoteModelContext
from ..._base.attribute import AttributeModel, Attribute


# noinspection PyAbstractClass
class RemoteAuthoriser[AT: Authoriser](RemoteModel):
    model_config = ConfigDict(extra="forbid")

    cache: InstanceOf[ResponseCache] | None = Field(
        description=(
            "The cache to use for storing and retrieving responses instead of requesting from the API. "
            "If not provided, the authoriser will not use caching."
        ),
        default=None,
    )

    @abstractmethod
    def create_authoriser(self) -> AT:
        """Create an authoriser for the API using the configured credentials."""
        raise NotImplementedError


# noinspection PyAbstractClass
class RemoteAPI[AT: RemoteAuthoriser](HasEndpoints):
    @classmethod
    def from_credentials(cls, credentials: Mapping[str, Any]) -> Self:
        """Create an authoriser for the API using the configured credentials."""
        authoriser = cls._create_authoriser(credentials)
        return cls.from_authoriser(authoriser)

    @classmethod
    def _create_authoriser(cls, credentials: Mapping[str, Any]) -> RemoteAuthoriser:
        auth_t = get_generic(cls, expected=RemoteAuthoriser, base=RemoteAPI)
        return auth_t.model_validate(credentials)

    @classmethod
    def from_authoriser(cls, authoriser: AT) -> Self:
        """Create an authoriser for the API using the configured authoriser."""
        handler = cls._create_handler(authoriser)
        return cls.model_validate(handler)

    @classmethod
    def _create_handler(cls, authoriser: AT) -> RequestHandler:
        return RequestHandler.create(
            authoriser=authoriser.create_authoriser(),
            cache=authoriser.cache,
            payload_handler=JSONPayloadHandler()
        )

    @model_validator(mode="before")
    @classmethod
    def _from_credentials[T](cls, value: T | Mapping[str, Any]) -> T | Self:
        if not isinstance(value, Mapping):
            return value

        with suppress(ValidationError):
            authoriser = cls._create_authoriser(value)
            handler = cls._create_handler(authoriser)
            return _map_handler(cls, handler)

        return value

    @model_validator(mode="before")
    @classmethod
    def _from_authoriser[T](cls, value: T | RemoteAuthoriser) -> T | Self:
        if not isinstance(value, RemoteAuthoriser):
            return value

        handler = cls._create_handler(value)
        return _map_handler(cls, handler)

    @classmethod
    def create_uri(cls, value: Any, kind: str | None = None) -> URI:
        """Create a URI for the source handled by this API model from the given ID and type."""
        context = RemoteModelContext(type=kind)
        return URI.get_adapter_for_source(cls.source).validate_python(value, context=context)


class HasAPI[API: RemoteAPI](AttributeModel, HasLogger):
    api: Annotated[API, Attribute()] = Field(
        description="The API client model used to interact with the remote service."
    )

    @staticmethod
    def _get_endpoints(api: Endpoints | HasEndpoints, key: str | None) -> Endpoints | HasEndpoints:
        if not key:
            return api

        for key in key.split("."):
            if not hasattr(api, key):
                raise EndpointsError(f"API does not have attribute '{key}'.")
            api = getattr(api, key)

        return api

    @classmethod
    def _validate_api[T](
            cls,
            kind: str,
            invalid_return: T,
            *expected: tuple[str | None, type[Endpoints | HasEndpoints], str]
    ) -> Callable:
        async def invalid_wrapper() -> T:
            if callable(invalid_return):
                return invalid_return()
            return invalid_return

        def decorator(func: Callable) -> Callable:
            @functools.wraps(func)
            def wrapper(self: HasAPI, *args, **kwargs):
                for key, expected_type, context in expected:
                    endpoints = self._validate_endpoints(key=key, context=context, expected=expected_type, name=kind)
                    if endpoints is None:
                        return invalid_wrapper()

                return func(self, *args, **kwargs)

            return wrapper
        return decorator

    def _validate_endpoints[T](self, key: str, expected: type[T], context: str, name: str = "") -> T | None:
        api = self._get_endpoints(self.api, key)
        if isinstance(api, expected):
            return api

        source = self.api.source if isinstance(api, RemoteAPI) else "the"
        context = context.format(type=name)
        message = f"Cannot run {source} operation for {name or key}. API does not support {context}."
        self._logger.warning(message)

        return None


# TODO: drop this on aiorequestful v2
class HasCache(HasEndpoints):
    @abstractmethod
    async def _setup_cache(self, cache: ResponseCache) -> None:
        """Set up the repositories and repository getter on the self.handler.session's cache."""
        raise NotImplementedError

    async def __aenter__(self) -> Self:
        await super().__aenter__()

        handler = self._handler
        session = handler.session

        if isinstance(session, CachedSession):
            cache = session.cache
            with suppress(CacheError):
                await self._setup_cache(cache)

            for repository in cache.values():
                # all repositories must use the same payload handler as the request handler
                # for it to function correctly
                repository.settings.payload_handler = handler.payload_handler

        return self
