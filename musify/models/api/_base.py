import contextlib
import functools
from abc import abstractmethod
from collections.abc import Mapping, Callable
from typing import Self, Any, Annotated

from aiorequestful.auth import Authoriser
from aiorequestful.cache.backend import ResponseCache
from aiorequestful.request import RequestHandler
from aiorequestful.response.payload import JSONPayloadHandler
from pydantic import model_validator, ModelWrapValidatorHandler, InstanceOf, Field, ValidationError, ConfigDict
from typing_inspection.typing_objects import is_typevar

from musify.models.api._endpoints import HasEndpoints, Endpoints
from musify.models.exception import EndpointsError
from musify.models.metadata import Attribute
from musify.models.properties.logger import HasLogger
from musify.models.remote import RemoteModel


# noinspection PyAbstractClass
class RemoteAuthoriser[AT: Authoriser](RemoteModel):
    model_config = ConfigDict(extra="forbid")

    cache: InstanceOf[ResponseCache] | None = Field(
        description="A cache for storing responses. If not provided, the authoriser will not use caching.",
        default=None,
    )

    @abstractmethod
    def create_authoriser(self) -> AT:
        """Create an authoriser for the API using the configured credentials."""
        raise NotImplementedError


class RemoteAPI[AT: RemoteAuthoriser](HasEndpoints):
    @model_validator(mode="wrap")
    @classmethod
    def _from_authoriser[T](cls, value: T | RemoteAuthoriser, handler: ModelWrapValidatorHandler[Self]) -> Self:
        key = "authoriser"
        if isinstance(value, Mapping) and set(value.keys()) == {key}:
            value = value[key]
        if not isinstance(value, RemoteAuthoriser):
            return handler(value)

        request_handler = RequestHandler.create(
            authoriser=value.create_authoriser(), cache=value.cache, payload_handler=JSONPayloadHandler()
        )
        return handler(request_handler)

    @model_validator(mode="wrap")
    @classmethod
    def _from_credentials[T](cls, value: T | RemoteAuthoriser, handler: ModelWrapValidatorHandler[Self]) -> Self:
        if not isinstance(value, Mapping):
            return handler(value)

        with contextlib.suppress(ValidationError):
            value = cls._create_authoriser_from_credentials(value)

        return handler(value)

    @classmethod
    def _create_authoriser_from_credentials(cls, credentials: Mapping[str, Any]) -> AT:
        base = next(
            (base for base in cls.__pydantic_parent_namespace__["bases"] if issubclass(base, RemoteAPI)), None
        )
        if base is None:
            base = cls

        generics = base.__pydantic_generic_metadata__["args"]
        if all(is_typevar(arg) for arg in generics):
            generics = cls.__pydantic_generic_metadata__["args"]

        auth_t = next(arg for arg in generics if not is_typevar(arg) and issubclass(arg, RemoteAuthoriser))
        return auth_t.model_validate(credentials)

    # TODO: figure out cache
        # try:
        #     await self._setup_cache()
        # except CacheError:
        #     pass
        #
        # session = handler.session
        # if isinstance(session, CachedSession):
        #     for repository in session.cache.values():
        #         # all repositories must use the same payload handler as the request handler
        #         # for it to function correctly
        #         repository.settings.payload_handler = self.handler.payload_handler


class HasAPI[API: RemoteAPI](RemoteModel, HasLogger):
    api: Annotated[API, Attribute()] = Field(
        description="The API client model used to interact with the remote service.."
    )

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
                    api = cls._get_endpoints(self.api, key)

                    if not isinstance(api, expected_type):
                        context = context.format(type=kind)
                        message = (
                            f"Cannot run {self.source.title()} operation for {kind}. "
                            f"API does not support {context}."
                        )
                        self.logger.warning(message)
                        return invalid_wrapper()

                return func(self, *args, **kwargs)

            return wrapper
        return decorator

    @staticmethod
    def _get_endpoints(api: Endpoints | HasEndpoints, key: str | None) -> Endpoints | HasEndpoints:
        if not key:
            return api

        for key in key.split("."):
            if not hasattr(api, key):
                raise EndpointsError(f"API does not have attribute '{key}'.")
            api = getattr(api, key)

        return api
