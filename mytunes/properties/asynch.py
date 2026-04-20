from asyncio import Semaphore
from typing import Annotated, Any

from pydantic import Field
from pydantic import GetCoreSchemaHandler, GetJsonSchemaHandler
from pydantic.json_schema import JsonSchemaValue
from pydantic_core import core_schema, CoreSchema

from .._base.attribute import AttributeModel


class _SemaphoreSchema:
    # noinspection PyUnusedLocal
    @classmethod
    def __get_pydantic_core_schema__(cls, source: Any, handler: GetCoreSchemaHandler) -> CoreSchema:
        cast_int_schema = core_schema.chain_schema(
            [
                core_schema.int_schema(),
                core_schema.no_info_plain_validator_function(lambda x: Semaphore(x)),
            ]
        )
        python_schema = core_schema.union_schema(
            [
                core_schema.is_instance_schema(Semaphore),
                cast_int_schema,
            ]
        )

        # noinspection PyProtectedMember
        return core_schema.json_or_python_schema(
            json_schema=core_schema.int_schema(),
            python_schema=python_schema,
            serialization=core_schema.plain_serializer_function_ser_schema(lambda x: int(x._value), when_used="json")
        )

    @classmethod
    def __get_pydantic_json_schema__(
        cls, _core_schema: CoreSchema, handler: GetJsonSchemaHandler
    ) -> JsonSchemaValue:
        return handler(core_schema.int_schema())


SemaphoreT = Annotated[
    Semaphore, _SemaphoreSchema
]


class HasAsyncOperations(AttributeModel):
    concurrency: SemaphoreT = Field(
        description=(
            "The max concurrency of IO tasks (i.e. loading/saving) of files in this library. "
            "Setting this too low will reduce the speed of these operations. "
            "Setting this too high will cause these operations to hang."
        ),
        default=32,
        repr=False,
    )
