from collections.abc import Iterable
from typing import Literal, get_type_hints

from pydantic.fields import FieldInfo

from .._models import AttributeModel
from mytunes._types import get_base_types
from .._models.item.track import Track
from .._models.properties.audio import HasAudioProperties
from .._models.properties.date import HasAddedDate, HasPlayedDate
from .._models.properties.file import IsLocalFile
from ..exception import MyTunesTypeError


def get_tag_attributes_map[T](expected: type[T] | None = None) -> dict[str, type[T]]:
    fields_map: dict[str, type[T]] = {}
    for kls in _ATTRIBUTE_FIELD_TYPES:
        for field_name in kls.__tag_attributes__:
            field = get_tag_from_expected(kls, field_name, expected)
            if field is not None:
                fields_map[field_name] = field

    return fields_map


def get_tag_attributes_type(expected: type[AttributeModel] | None = None) -> type[Literal]:
    names = tuple(get_tag_attributes_map(expected))
    return Literal[*names]


def get_tag_from_expected[T](
        kls: type[AttributeModel], name: str, expected: type[T] | None = None
) -> type[T] | None:
    if expected is None:
        return kls

    match kls.get_field_info(name):
        case FieldInfo() as field:
            annotation = field.annotation
        case property() as prop:
            annotation = get_type_hints(prop.fget, include_extras=True)["return"]
        case annotation:
            raise MyTunesTypeError(f"Unknown field type: {annotation}")

    types = get_base_types(annotation, resolve_generics=True)
    if any(issubclass(t, expected) for t in types):
        return kls


_ATTRIBUTE_FIELD_TYPES: frozenset[type[AttributeModel]] = frozenset({
    Track,
    IsLocalFile,
    HasAudioProperties,
    HasAddedDate,
    HasPlayedDate,
})
_ATTRIBUTE_FIELD_MAP = get_tag_attributes_map()
_ATTRIBUTE_FIELD_TYPE = get_tag_attributes_type()
