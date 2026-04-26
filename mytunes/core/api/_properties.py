# TODO: drop this whole script on aiorequestful v2
from collections.abc import Mapping, MutableMapping
from datetime import timedelta
from typing import Any, Annotated, Union

from aiorequestful.cache.backend import ResponseCache, SQLiteCache, CACHE_TYPES
from aiorequestful.timer import GeometricCountTimer, StepCeilingTimer
from pydantic import PositiveInt, Field, NonNegativeFloat, GetCoreSchemaHandler, Tag, GetJsonSchemaHandler
from pydantic.json_schema import JsonSchemaValue
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

    @classmethod
    def __get_pydantic_json_schema__(
            cls, _core_schema: CoreSchema, handler: GetJsonSchemaHandler
    ) -> JsonSchemaValue:
        return handler(core_schema.plain_serializer_function_ser_schema(cls._serialise))

    @staticmethod
    def _serialise(timer: GeometricCountTimer) -> JsonSchemaValue:
        return {"initial": timer.initial, "count": timer.count, "factor": timer.factor}


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

    @classmethod
    def __get_pydantic_json_schema__(
            cls, _core_schema: CoreSchema, handler: GetJsonSchemaHandler
    ) -> JsonSchemaValue:
        return handler(core_schema.plain_serializer_function_ser_schema(cls._serialise))

    @staticmethod
    def _serialise(timer: StepCeilingTimer) -> JsonSchemaValue:
        return {"initial": timer.initial, "final": timer.final, "step": timer.step}


type WaitTimerT = Annotated[StepCeilingTimer, _StepCeilingTimer]


class Timers(BaseModel):
    retry: RetryTimerT | None = Field(
        description="Configuration for the timer that controls how long to wait "
                    "in between each successive failed request",
        default=None,
    )
    wait: WaitTimerT | None = Field(
        description="Configuration for the timer that controls how long to wait after every request,"
                    " regardless of whether it was successful.",
        default=None,
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

    @classmethod
    def __get_pydantic_json_schema__(
            cls, _core_schema: CoreSchema, handler: GetJsonSchemaHandler
    ) -> JsonSchemaValue:
        return handler(core_schema.plain_serializer_function_ser_schema(cls._serialise))

    @staticmethod
    def _serialise(cache: SQLiteCache) -> JsonSchemaValue:
        return {"expire": str(cache.expire.total_seconds())}

type ResponseCacheT = Annotated[SQLiteCache, _SQLiteCacheType]


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
