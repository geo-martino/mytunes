import contextlib
from abc import abstractmethod
from collections.abc import Mapping
from typing import Self, Any

from aiorequestful.auth import Authoriser
from aiorequestful.cache.backend import ResponseCache
from aiorequestful.request import RequestHandler
from aiorequestful.response.payload import JSONPayloadHandler
from pydantic import model_validator, ModelWrapValidatorHandler, InstanceOf, Field, ValidationError, ConfigDict
from typing_inspection.typing_objects import is_typevar

from musify.exception import MusifyValueError
from musify.remote import RemoteModel
from musify.remote.api._endpoints import HasEndpoints


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
    def _from_handler[T](cls, value: T | RequestHandler, handler: ModelWrapValidatorHandler[Self]) -> Self:
        key = "handler"
        if isinstance(value, Mapping) and set(value.keys()) == {key}:
            value = value[key]
        if not isinstance(value, RequestHandler):
            return handler(value)

        data = {name: {key: value} for name in cls.model_fields.keys()}
        return handler(data)

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

    @model_validator(mode="after")
    def _all_handlers_are_the_same(self) -> Self:
        # noinspection PyProtectedMember
        handlers = {id(getattr(self, field_name)._handler) for field_name in self.__class__.model_fields.keys()}
        if len(handlers) != 1:
            raise MusifyValueError(
                "All endpoint models must use the same request handler for API to function correctly."
            )

        return self

    async def __aenter__(self) -> Self:
        # noinspection PyProtectedMember
        handler: RequestHandler = next(
            getattr(self, field_name)._handler for field_name in self.__class__.model_fields.keys()
        )
        await handler.__aenter__()

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

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        for field_name in self.__class__.model_fields.keys():
            # noinspection PyProtectedMember
            handler: RequestHandler = getattr(self, field_name)._handler
            if not handler.closed:
                await handler.__aexit__(exc_type, exc_val, exc_tb)
