import contextlib
import functools
import inspect
from collections.abc import Sequence
from typing import Any, get_args, Callable, Self, Annotated

from pydantic import GetCoreSchemaHandler, GetJsonSchemaHandler, TypeAdapter
from pydantic.json_schema import JsonSchemaValue
from pydantic_core import core_schema, CoreSchema
from typing_inspection.typing_objects import is_typevar
from yarl import URL

from musify.exception import MusifyTypeError, MusifyValueError
from musify.models.properties.uri import URI, HasURI, HasImmutableURI
from musify.models.remote import RemoteModel
from musify.models.url import HttpURL


class _ApiSchemaBase[UT: URI, MT: HasURI]:
    @staticmethod
    def _get_param_position(func: Callable, param_key: str) -> int:
        if param_key not in (params := inspect.signature(func).parameters):
            param_keys = ", ".join(params)
            raise MusifyTypeError(f"Function must have a {param_key!r} parameter. Found: {param_keys}")
        return list(params).index(param_key)

    @classmethod
    def _create_type_from_model_generics(cls, model: RemoteModel) -> type[Self]:
        from musify.models.api import Endpoints
        generics = ()
        while not generics:
            base = next(
                base for base in model.__pydantic_parent_namespace__["bases"] if issubclass(base, Endpoints)
            )
            generics = base.__pydantic_generic_metadata__["args"]

            if all(is_typevar(arg) for arg in generics):
                generics = model.__pydantic_generic_metadata__["args"]

            model = base

        uri_t = next(arg for arg in generics if not is_typevar(arg) and issubclass(arg, URI))
        model_t = next(arg for arg in generics if not is_typevar(arg) and issubclass(arg, HasImmutableURI))
        return cls[uri_t, model_t]

    @staticmethod
    def _pop_value_from_args_or_kwargs[T](
            args: list[T], kwargs: dict, param_idx: int, param_key: str
    ) -> tuple[list[T], Any, list[T]]:
        if param_key in kwargs:
            value = kwargs.pop(param_key)
            return args[:param_idx], value, args[param_idx:]
        with contextlib.suppress(IndexError):
            value = args.pop(param_idx)
            return args[:param_idx], value, args[param_idx:]

        raise MusifyValueError(f"{param_key!r} value is required.")


class _ApiURLSchema[UT: URI, MT: HasURI](_ApiSchemaBase[UT, MT]):
    @classmethod
    def __get_pydantic_core_schema__(cls, source: Any, handler: GetCoreSchemaHandler) -> CoreSchema:
        args = get_args(source)
        if not args:
            raise MusifyTypeError(f"Must define generic types for {type(source)}")

        uri_t: UT = args[0]
        model_t: type[MT] = args[1]

        url_schema = handler.generate_schema(HttpURL)

        def _from_api_uri(url: URL) -> URL:
            uri = TypeAdapter(uri_t).validate_python(url)
            if not str(url).startswith(str(uri.api_url)):
                raise ValueError("URL does not match the expected API URL format.")
            return url

        from_api_url_schema = core_schema.chain_schema(
            [
                url_schema,
                core_schema.no_info_plain_validator_function(_from_api_uri),
            ]
        )

        def _from_uri(uri: URI) -> URL:
            return uri.api_url

        from_public_url_schema = core_schema.chain_schema(
            [
                url_schema,
                handler.generate_schema(uri_t),
                core_schema.no_info_plain_validator_function(_from_uri),
            ]
        )

        from_uri_schema = core_schema.chain_schema(
            [
                handler.generate_schema(uri_t),
                core_schema.no_info_plain_validator_function(_from_uri),
            ]
        )

        def _from_model(model: HasURI) -> URL:
            uri = model.uri
            if uri is None:
                raise MusifyValueError("Model does not have a URI.")
            return _from_uri(uri)

        from_model_schema = core_schema.chain_schema(
            [
                handler.generate_schema(model_t),
                core_schema.no_info_plain_validator_function(_from_model),
            ]
        )

        def _from_id(value: str) -> URL:
            uri = uri_t.from_id(value, kind=model_t.type)
            return _from_uri(uri)

        from_id_schema = core_schema.chain_schema(
            [
                core_schema.str_schema(),
                core_schema.no_info_plain_validator_function(_from_id),
            ]
        )

        python_schema = core_schema.union_schema(
            [
                from_api_url_schema,
                from_public_url_schema,
                from_uri_schema,
                from_model_schema,
                from_id_schema
            ],
            mode="left_to_right",
        )

        return core_schema.json_or_python_schema(
            json_schema=url_schema,
            python_schema=python_schema,
            serialization=core_schema.to_string_ser_schema()
        )

    @classmethod
    def __get_pydantic_json_schema__(
            cls, _core_schema: CoreSchema, handler: GetJsonSchemaHandler
    ) -> JsonSchemaValue:
        return handler(core_schema.url_schema())

    @classmethod
    def validate_call[T: Callable](cls, func: T) -> T:
        """
        Decorator to validate and convert a URL argument for API endpoint methods.

        WORKAROUND: Since Pydantic does not yet support generic types in validate_call,
        this decorator extracts the generic types from the decorated method's class and uses a TypeAdapter
        to validate and convert the URL argument to a URL using ApiURL's core schema.

        This should be removed once the validate_call issue is resolved:
        https://github.com/pydantic/pydantic/issues/7796
        """
        param_key = "url"
        param_idx = cls._get_param_position(func, param_key)

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            args = list(args)

            self = args.pop(0)
            cls_t = cls._create_type_from_model_generics(self)
            adapter = TypeAdapter(cls_t)

            args_prev, value, args_next = cls._pop_value_from_args_or_kwargs(args, kwargs, param_idx - 1, param_key)
            url = adapter.validate_python(value)

            return func(self, *args_prev, url, *args_next, **kwargs)
        return wrapper


type ApiURL[UT: URI, MT: HasURI] = Annotated[URL, _ApiURLSchema[UT, MT]]


class _ApiURISchema[UT: URI, MT: HasURI](_ApiSchemaBase[UT, MT]):
    @classmethod
    def __get_pydantic_core_schema__(cls, source: Any, handler: GetCoreSchemaHandler) -> CoreSchema:
        args = get_args(source)
        if not args:
            raise MusifyTypeError(f"Must define generic types for {type(source)}")

        uri_t: UT = args[0]
        model_t: type[MT] = args[1]

        uri_schema = handler.generate_schema(uri_t)

        from_url_schema = core_schema.chain_schema(
            [
                handler.generate_schema(HttpURL),
                uri_schema,
            ]
        )

        def _from_model(model: HasURI) -> URI:
            if model.uri is None:
                raise MusifyValueError("Model does not have a URI.")
            return model.uri

        from_model_schema = core_schema.chain_schema(
            [
                handler.generate_schema(model_t),
                core_schema.no_info_plain_validator_function(_from_model),
            ]
        )

        def _from_id(value: str) -> URI:
            return uri_t.from_id(value, kind=model_t.type)

        from_id_schema = core_schema.chain_schema(
            [
                core_schema.str_schema(),
                core_schema.no_info_plain_validator_function(_from_id),
            ]
        )

        python_schema = core_schema.union_schema(
            [
                uri_schema,
                from_url_schema,
                from_model_schema,
                from_id_schema,
            ],
            mode="left_to_right",
        )

        return core_schema.json_or_python_schema(
            json_schema=uri_schema,
            python_schema=python_schema,
            serialization=core_schema.to_string_ser_schema()
        )

    @classmethod
    def __get_pydantic_json_schema__(
            cls, _core_schema: CoreSchema, handler: GetJsonSchemaHandler
    ) -> JsonSchemaValue:
        return handler(core_schema.str_schema())

    @classmethod
    def validate_call[T: Callable](cls, func: T) -> T:
        """
        Decorator to validate and convert a URL argument for API endpoint methods.

        WORKAROUND: Since Pydantic does not yet support generic types in validate_call,
        this decorator extracts the generic types from the decorated method's class and uses a TypeAdapter
        to validate and convert the URL argument to a URL using ApiURL's core schema.

        This should be removed once the validate_call issue is resolved:
        https://github.com/pydantic/pydantic/issues/7796
        """
        try:
            param_key = "uri"
            param_idx = cls._get_param_position(func, param_key)
            is_sequence = False
        except MusifyTypeError:
            param_key = "uris"
            param_idx = cls._get_param_position(func, param_key)
            is_sequence = True

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            args = list(args)

            self = args.pop(0)
            cls_t = cls._create_type_from_model_generics(self)
            # noinspection PyTypeHints
            if not is_sequence:
                adapter = TypeAdapter(cls_t)
            else:
                adapter = TypeAdapter(Sequence[cls_t])

            args_prev, value, args_next = cls._pop_value_from_args_or_kwargs(args, kwargs, param_idx - 1, param_key)

            uris = adapter.validate_python(value)

            return func(self, *args_prev, uris, *args_next, **kwargs)
        return wrapper


type ApiURI[UT: URI, MT: HasURI] = Annotated[UT, _ApiURISchema[UT, MT]]
type ApiURISequence[UT: URI, MT: HasURI] = Sequence[ApiURI[UT, MT]]
