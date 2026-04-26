# TODO: drop this whole script on aiorequestful v2
from collections.abc import Mapping, MutableMapping
from datetime import timedelta
from typing import Any, Annotated, Union

from aiorequestful.cache.backend import ResponseCache, SQLiteCache, CACHE_TYPES
from aiorequestful.timer import GeometricCountTimer, StepCeilingTimer
from pydantic import PositiveInt, Field, NonNegativeFloat, GetCoreSchemaHandler, Tag
from pydantic_core import CoreSchema, core_schema

from mytunes._base import BaseModel
from mytunes.exception import MyTunesValidationError


class _GeometricCountTimerType:
    @classmethod
    def __get_pydantic_core_schema__(cls, source: Any, handler: GetCoreSchemaHandler) -> CoreSchema:
        instance_schema = core_schema.is_instance_schema(GeometricCountTimer)

        initial_field = core_schema.float_schema(ge=0)
        count_field = core_schema.union_schema([
            core_schema.float_schema(ge=0),
            core_schema.none_schema(),
        ])
        factor_field = core_schema.float_schema(ge=1)

        fields_schema = core_schema.typed_dict_schema({
            "initial": core_schema.typed_dict_field(initial_field, required=False),
            "count": core_schema.typed_dict_field(count_field, required=False),
            "factor": core_schema.typed_dict_field(factor_field, required=False),
        })
        model_schema = core_schema.chain_schema([
            fields_schema,
            core_schema.no_info_plain_validator_function(lambda data: GeometricCountTimer(**data)),
        ])

        return core_schema.union_schema([instance_schema, model_schema])


type RetryTimerT = Annotated[GeometricCountTimer, _GeometricCountTimerType]


class _StepCeilingTimer:
    @classmethod
    def __get_pydantic_core_schema__(cls, source: Any, handler: GetCoreSchemaHandler) -> CoreSchema:
        instance_schema = core_schema.is_instance_schema(StepCeilingTimer)

        initial_field = core_schema.float_schema(ge=0)
        final_field = core_schema.float_schema(ge=0)
        step_field = core_schema.float_schema(ge=0)

        fields_schema = core_schema.typed_dict_schema({
            "initial": core_schema.typed_dict_field(initial_field, required=False),
            "final": core_schema.typed_dict_field(final_field, required=False),
            "step": core_schema.typed_dict_field(step_field, required=False),
        })
        model_schema = core_schema.chain_schema([
            fields_schema,
            core_schema.no_info_plain_validator_function(lambda data: StepCeilingTimer(**data)),
            instance_schema,
        ])

        return core_schema.union_schema([instance_schema, model_schema])


type WaitTimerT = Annotated[StepCeilingTimer, _StepCeilingTimer]


class Timers(BaseModel):
    retry: RetryTimerT = Field(
        description="Configuration for the timer that controls how long to wait "
                    "in between each successive failed request",
        default_factory=GeometricCountTimer,
    )
    wait: WaitTimerT = Field(
        description="Configuration for the timer that controls how long to wait after every request,"
                    " regardless of whether it was successful.",
        default_factory=StepCeilingTimer,
    )


class _SQLiteCacheType:
    @classmethod
    def __get_pydantic_core_schema__(cls, source: Any, handler: GetCoreSchemaHandler) -> CoreSchema:
        instance_schema = core_schema.is_instance_schema(SQLiteCache)

        path_field = core_schema.str_schema()
        expire_field = core_schema.timedelta_schema()

        fields_schema = core_schema.typed_dict_schema({
            "path": core_schema.typed_dict_field(path_field),
            "expire": core_schema.typed_dict_field(expire_field, required=False),
        })
        model_schema = core_schema.chain_schema([
            fields_schema,
            core_schema.no_info_plain_validator_function(lambda data: SQLiteCache.connect_with_path(**data)),
        ])

        return core_schema.union_schema([instance_schema, model_schema])


type ResponseCacheT = Annotated[SQLiteCache, _SQLiteCacheType]


# class APICacheConfig(Instantiator[ResponseCache]):
#     # noinspection PyTypeHints
#     type: Literal[*CACHE_TYPES] | None = Field(
#         description=f"The type of backend to connect to. Available types: {", ".join(CACHE_TYPES)}",
#         default=None,
#     )
#     db: str | Path = Field(
#         description="The DB to connect to e.g. the URI/path for connecting to an SQLite DB",
#         default=None,
#     )
#     expire_after: timedelta = Field(
#         description="The maximum permitted expiry time allowed when looking for a response in the cache. "
#                     "Also configures the expiry time to apply for new responses when persisting to the cache. "
#                     "Value can be a duration string i.e. [±]P[DD]DT[HH]H[MM]M[SS]S (ISO 8601 format for timedelta)",
#         default=api_cache_defaults.get("expire")
#     )
#
#     @computed_field(
#         description="Is this cache a file system cache that exists on the local system"
#     )
#     @property
#     def is_local(self) -> bool:
#         """Is this cache a file system cache that exists on the local system"""
#         cls = next((cls for cls in local_caches if cls.type == self.type), None)
#         return cls is not None
#
#     def create(self):
#         cls = next((cls for cls in CACHE_CLASSES if cls.type == self.type), None)
#         return cls.connect(value=self.db, expire=self.expire_after)
#
#
# class APIConfig[T: RemoteAPI](Instantiator[T], metaclass=ABCMeta):
#     cache: APICacheConfig = Field(
#         description="Configuration for the API cache",
#         default_factory=APICacheConfig,
#     )
#     handler: APIHandlerConfig = Field(
#         description="Configuration for the API handler",
#         default_factory=APIHandlerConfig,
#     )
#     token_file_path: Path | None = Field(
#         description="A path to save/load a response token to",
#         default=None,
#     )
#
#
# class SpotifyAPIConfig(APIConfig[SpotifyAPI]):
#     client_id: SecretStr = Field(
#         description="The client ID to use when authorising requests",
#     )
#     client_secret: SecretStr = Field(
#         description="The client secret to use when authorising requests",
#     )
#     scope: tuple[str, ...] = Field(
#         description="The scopes to request access to",
#         default=()
#     )
#
#     # noinspection PyNestedDecorators
#     @field_validator("client_id", "client_secret", mode="after")
#     @classmethod
#     def validate_secrets(cls, value: SecretStr) -> SecretStr:
#         """Ensure the API has the correct secret credentials set."""
#         if not value:
#             raise ParserError("Cannot create API object without both client ID and client secret set")
#         return value
#
#     def create(self):
#         api = SpotifyAPI(
#             client_id=self.client_id.get_secret_value(),
#             client_secret=self.client_secret.get_secret_value(),
#             scope=self.scope,
#             cache=self.cache.create(),
#             token_file_path=self.token_file_path,
#         )
#         api.handler.retry_timer = self.handler.retry.create()
#         api.handler.wait_timer = self.handler.wait.create()
#
#         return api


if __name__ == "__main__":
    import asyncio
    from pydantic import TypeAdapter

    adapter = TypeAdapter(_GeometricCountTimerType)
    model = adapter.validate_python({})
    print(type(model), model.initial, model.count, model.factor)
    model = adapter.validate_python(model)
    print(type(model), model.initial, model.count, model.factor)

    adapter = TypeAdapter(_StepCeilingTimer)
    model = adapter.validate_python({})
    print(type(model), model.initial, model.final, model.step)
    model = adapter.validate_python(model)
    print(type(model), model.initial, model.final, model.step)

    print(Timers())

    adapter = TypeAdapter(ResponseCacheT)
    model: SQLiteCache = adapter.validate_python({"type": "sqlite", "path": "sqlite:///test.db"})
    print(type(model), model, model.expire)
    async def main():
        async with model:
            print(type(model), model.connection)

    asyncio.run(main())
