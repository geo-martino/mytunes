from enum import IntEnum
from typing import Any, Self

from pydantic import GetCoreSchemaHandler, GetJsonSchemaHandler
from pydantic.alias_generators import to_snake
from pydantic.json_schema import JsonSchemaValue
from pydantic_core import CoreSchema, core_schema

from musify._models.exception import MusifyValidationError


class IntEnumModel(IntEnum):
    """
    Expands the IntEnum to allow usage as a Pydantic model

    Adds support for:
    - Validation from both integers and strings which represent the name of the enum member
    """

    # noinspection PyUnusedLocal
    @classmethod
    def __get_pydantic_core_schema__(cls, source: Any, handler: GetCoreSchemaHandler) -> CoreSchema:
        return core_schema.no_info_after_validator_function(
            cls._construct,
            core_schema.union_schema(
                [core_schema.str_schema(), core_schema.int_schema()]
            ),
            serialization=core_schema.plain_serializer_function_ser_schema(lambda x: x.name),
        )

    # noinspection PyUnusedLocal
    @classmethod
    def __get_pydantic_json_schema__(cls, schema: CoreSchema, handler: GetJsonSchemaHandler) -> JsonSchemaValue:
        return {'enum': [m.name for m in cls], 'type': 'string'}

    @classmethod
    def _construct(cls, value: Any) -> Self:
        match value:
            case str():
                return cls[to_snake(value).upper()]
            case int():
                return cls(value)
            case _:
                raise MusifyValidationError(f"Cannot get enum for {value!r}")
