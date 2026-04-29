import functools
from abc import abstractmethod
from collections.abc import Mapping, Callable, Awaitable
from contextlib import suppress, AbstractAsyncContextManager
from types import UnionType
from typing import Self, Any, Annotated

from aiorequestful.auth import Authoriser
from aiorequestful.cache.backend import ResponseCache
from aiorequestful.cache.exception import CacheError
from aiorequestful.cache.session import CachedSession
from aiorequestful.request import RequestHandler
from aiorequestful.response.payload import JSONPayloadHandler
from pydantic import model_validator, Field, ValidationError, ConfigDict

from mytunes._types import get_generic, get_base_types
from mytunes.core.api._endpoints import HasEndpoints, Endpoints, _map_handler
from mytunes.core.properties.logger import HasLogger
from mytunes.core.properties.uri import URI
from mytunes.core.remote import RemoteModel
from mytunes.exception import APIError, APIModelError
from ._properties import ResponseCacheT, Timers
from .._context import RemoteModelContext
from ..._base.attribute import AttributeModel, Attribute


# noinspection PyAbstractClass
class RemoteAuthoriser[AT: Authoriser](RemoteModel, Timers):
    model_config = ConfigDict(extra="forbid")

    cache: ResponseCacheT | None = Field(
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
class RemoteAPI[AT: RemoteAuthoriser](RemoteModel, AbstractAsyncContextManager):
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
        handler = RequestHandler.create(
            authoriser=authoriser.create_authoriser(),
            cache=authoriser.cache,
            payload_handler=JSONPayloadHandler()
        )

        # TODO: drop this on aiorequestful v2
        handler.retry_timer = authoriser.retry
        handler.wait_timer = authoriser.wait
        return handler

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

    async def __aenter__(self) -> Self:
        await self.api.__aenter__()
        return await super().__aenter__()

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.api.__aexit__(exc_type, exc_val, exc_tb)
        return await super().__aexit__(exc_type, exc_val, exc_tb)


def validate_api[T](invalid_return: T, *endpoints: type[Endpoints | HasEndpoints] | UnionType) -> Callable:
    def decorator(func: Callable[Any, Awaitable[T]]) -> Callable[Any, Awaitable[T]]:
        @functools.wraps(func)
        async def wrapper(self, *args, **kwargs):
            if not isinstance(self, HasAPI):
                raise APIModelError(f"Cannot validate API, {type(self).__name__!r} does not support API models.")

            api = self.api
            source = api.source if isinstance(api, RemoteAPI) and isinstance(api.source, str) else "the"
            log = f"Cannot run {source} operation: {func.__name__!r}"

            types: list[str] = []
            for endpoint in endpoints:
                errors: list[APIError] = []

                for ep in get_base_types(endpoint):  # try to get the first matching endpoints type
                    ep: type[Endpoints | HasEndpoints]
                    try:
                        api = ep.validate_api(api, *types)
                        errors.clear()
                        break
                    except APIError as exc:
                        errors.append(exc)

                if errors:
                    self._logger.warning(f"{log}: {" | ".join(map(str, errors))}")
                    return invalid_return() if callable(invalid_return) else invalid_return

                if isinstance(endpoint, type) and issubclass(endpoint, HasEndpoints):
                    types.append(next(iter(endpoint.get_endpoint_names())))

            return await func(self, *args, **kwargs)
        return wrapper
    return decorator


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
