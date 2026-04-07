from typing import Literal, get_type_hints

from pydantic.fields import FieldInfo

from .._models import AttributeModel
from musify._types import get_base_types
from .._models.item.track import Track
from .._models.properties.audio import HasAudioProperties
from .._models.properties.date import HasAddedDate, HasPlayedDate
from .._models.properties.file import IsLocalFile
from ..exception import MusifyTypeError


def get_tag_fields_map[T](expected: type[T] | None = None) -> dict[str, type[T]]:
    fields_map: dict[str, type[T]] = {}
    for kls in _TAG_FIELD_TYPES:
        for field_name in kls.__tag_attributes__:
            if expected is None:
                fields_map[field_name] = kls
                continue

            match kls.get_field_info(field_name):
                case FieldInfo() as field:
                    annotation = field.annotation
                case property() as prop:
                    annotation = get_type_hints(prop.fget, include_extras=True)["return"]
                case annotation:
                    raise MusifyTypeError(f"Unknown field type: {annotation}")

            types = get_base_types(annotation, resolve_generics=True)
            if any(issubclass(t, expected) for t in types):
                fields_map[field_name] = kls

    return fields_map


def get_tag_fields_type(expected: type[AttributeModel] | None = None) -> type[Literal]:
    names = tuple(get_tag_fields_map(expected))
    return Literal[*names]


_TAG_FIELD_TYPES: frozenset[type[AttributeModel]] = frozenset({
    Track,
    IsLocalFile,
    HasAudioProperties,
    HasAddedDate,
    HasPlayedDate,
})
_TAG_FIELD_MAP = get_tag_fields_map()
_TAG_FIELD_TYPE = get_tag_fields_type()
