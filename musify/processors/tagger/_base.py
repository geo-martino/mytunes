from typing import Any

from pydantic.fields import FieldInfo
from typing_inspection.typing_objects import is_typevar

from .._types import get_tag_fields_type
from ..._models import ModelMetaclass, BaseModel, AttributeModel


class TaggerMetaclass(ModelMetaclass):
    def __new__(mcs, cls_name: str, bases: tuple[type[Any], ...], namespace: dict[str, Any], **kwargs: Any):
        # set appropriate field types from the generic type
        base = next((base for base in bases if isinstance(base, mcs) and issubclass(base, BaseModel)), None)
        generics = next((base.__pydantic_generic_metadata__["args"] for base in bases if isinstance(base, mcs)), None)
        info = base.model_fields.get("field") if base is not None else None
        if info is not None:
            mcs._set_annotation_from_generic_type(info, generics)

        return super().__new__(mcs, cls_name, bases, namespace, **kwargs)

    @classmethod
    def _set_annotation_from_generic_type(cls, info: FieldInfo, generics: list[type[AttributeModel]]) -> None:
        attribute_type = generics[1] if len(generics) > 1 else None
        if is_typevar(attribute_type):
            attribute_type = None
        info.annotation = get_tag_fields_type(attribute_type)
