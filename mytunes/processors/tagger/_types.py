from typing import Literal

from pydantic.fields import FieldInfo

from .._types import get_tag_from_expected, _ATTRIBUTE_FIELD_TYPES
from ..._base.attribute import AttributeModel
from mytunes.exception import MyTunesTypeError


def get_writeable_tag_attributes_map[T](expected: type[T] | None = None) -> dict[str, type[T]]:
    fields_map: dict[str, type[T]] = {}
    for kls in _ATTRIBUTE_FIELD_TYPES:
        for field_name in kls.__tag_attributes__:
            if not _attribute_is_writeable(kls, field_name):
                continue
            field = get_tag_from_expected(kls, field_name, expected)
            if field is not None:
                fields_map[field_name] = field

    return fields_map


def get_writeable_tag_attributes_type(expected: type[AttributeModel] | None = None) -> type[Literal]:
    names = tuple(get_writeable_tag_attributes_map(expected))
    return Literal[*names]


def _attribute_is_writeable(kls: type[AttributeModel], name: str) -> bool:
    match kls.get_field_info(name):
        case FieldInfo() as field:
            return not field.frozen
        case property() as prop:
            return prop.fset is not None
        case annotation:
            raise MyTunesTypeError(f"Unknown field type: {annotation}")


_WRITEABLE_ATTRIBUTE_FIELD_MAP = get_writeable_tag_attributes_map()
_WRITEABLE_ATTRIBUTE_FIELD_TYPE = get_writeable_tag_attributes_type()
