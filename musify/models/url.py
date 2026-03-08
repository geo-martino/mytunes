from typing import Annotated, Any

from pydantic import GetCoreSchemaHandler, GetJsonSchemaHandler
from pydantic.json_schema import JsonSchemaValue
from pydantic_core import core_schema
from yarl import URL as YarlURL


class _URLSchema:
    # noinspection PyUnusedLocal
    @classmethod
    def __get_pydantic_core_schema__(cls, source: Any, handler: GetCoreSchemaHandler) -> core_schema.CoreSchema:
        url_schema = core_schema.url_schema(host_required=True)
        cast_str_schema = core_schema.chain_schema(
            [
                url_schema,
                core_schema.no_info_plain_validator_function(lambda x: YarlURL(str(x))),
            ]
        )
        python_schema = core_schema.union_schema(
            [
                core_schema.is_instance_schema(YarlURL),
                cast_str_schema,
            ]
        )

        return core_schema.json_or_python_schema(
            json_schema=url_schema,
            python_schema=python_schema,
            serialization=core_schema.simple_ser_schema("str")
        )

    @classmethod
    def __get_pydantic_json_schema__(
        cls, _core_schema: core_schema.CoreSchema, handler: GetJsonSchemaHandler
    ) -> JsonSchemaValue:
        return handler(core_schema.url_schema())


HttpURL = Annotated[
    YarlURL, _URLSchema
]
