from collections.abc import Iterable
from contextlib import suppress
from functools import reduce
from typing import Any, cast, Self, get_type_hints

from mytunes._models.metadata import Attribute, TagAttribute
from mytunes._types import get_base_types
from mytunes.exception import MyTunesAttributeError, ModelError
from pydantic.fields import FieldInfo

from ._base import ModelMetaclass, BaseModel
from .resource import ResourceModel


class AttributeMetaclass(ModelMetaclass):
    """
    Metaclass for creating attribute models for this package.

    Expands on base model metaclass to add support for:
    - Setting tag attributes which are configured from the defined fields and properties of a model
    - Functionality for getting field info from a nested key using dot notation
    """
    def __new__(mcs, cls_name: str, bases: tuple[type[Any], ...], namespace: dict[str, Any], **kwargs: Any):
        cls = cast('type[AttributeModel]', super().__new__(mcs, cls_name, bases, namespace, **kwargs))

        metadata_fields = cls._metadata_fields

        if (key := "__tag_attributes__") in namespace:
            raise ModelError(f"Cannot define {key} on {cls.__name__!r} as it is a reserved name.")
        cls.__tag_attributes__ = frozenset(mcs._get_attribute_fields(metadata_fields))

        if (key := "__tag_fields__") in namespace:
            raise ModelError(f"Cannot define {key} on {cls.__name__!r} as it is a reserved name.")
        cls.__tag_fields__ = mcs._get_tag_fields(metadata_fields)

        return cls

    @classmethod
    def _get_attribute_fields(mcs, fields: dict[str, tuple[Any, list[Any]]]) -> set[str]:
        attributes = set()
        for field_name, (annotation, metadata) in fields.items():
            if not any(isinstance(meta, Attribute) for meta in metadata):
                continue

            attributes.add(field_name)
            attributes |= {
                f"{field_name}.{attr}"
                for kls in mcs._get_nested_models(annotation)
                for attr in kls.__tag_attributes__
            }

        return attributes

    @classmethod
    def _get_tag_fields(mcs, fields: dict[str, tuple[Any, list[Any]]]) -> dict[str, str]:
        tags = {}

        for field_name, (annotation, metadata) in fields.items():
            for meta in metadata:
                if not isinstance(meta, TagAttribute):
                    continue

                tag = meta.name if meta.name is not None else field_name
                tags[tag] = field_name
                tags |= {
                    f"{tag}.{attr}": f"{field_name}.{attr}"
                    for kls in mcs._get_nested_models(annotation)
                    if not issubclass(kls, ResourceModel)  # gets too messy and is not needed
                    for attr in kls.__tag_fields__
                }

        return tags

    @classmethod
    def _get_nested_models(mcs, annotation: Any) -> Iterable[Self]:
        for kls in get_base_types(annotation, ignore_none=True, resolve_generics=True):
            if isinstance(kls, type) and issubclass(kls, AttributeModel):
                yield kls

    def get_field_info(cls, key: str) -> FieldInfo | property:
        """Get field for a given key, supporting nested keys using dot notation."""
        kls = cast('type[AttributeModel]', cls)
        if len(key_split := key.split(".")) == 1:
            return AttributeMetaclass._get_field_info_from_model(kls, key)

        key_iter = iter(key_split[:-1])
        field = reduce(
            AttributeMetaclass._get_tag_field_from_field_info,
            key_iter,
            AttributeMetaclass._get_tag_field_from_field_info(kls, next(key_iter))
        )

        return AttributeMetaclass.get_field_info(field, key_split[-1])

    def _get_field_info_from_model(cls, key: str) -> FieldInfo:
        kls = cast('type[AttributeModel]', cls)
        match kls:
            case type() if issubclass(kls, BaseModel) and key in kls.model_fields:
                return kls.model_fields[key]
            case property():
                return AttributeMetaclass._get_tag_field_from_property(kls, key)
            case _:
                return getattr(kls, key)

    def _get_tag_field_from_field_info(cls, key: str) -> Any:
        kls = cast('type[AttributeModel]', cls)
        if key not in kls.model_fields:
            return getattr(cls, key)

        annotation = kls.model_fields[key].annotation
        return next(kls.__class__._get_nested_models(annotation), annotation)

    @classmethod
    def _get_tag_field_from_property(mcs, prop: property, key: str) -> Any:
        annotation = get_type_hints(prop.fget, include_extras=True)["return"]
        kls = next(mcs._get_nested_models(annotation), annotation)
        return mcs.get_field_info(kls, key)


class AttributeModel(BaseModel, metaclass=AttributeMetaclass):
    """
    A base class for creating attribute models in this package.

    Expands on the base model to add support for:
    - Getting and setting attributes from nested fields of models using dot notation
    """
    def __getattr__(self, key: str) -> Any:
        if len(key_split := key.split(".")) == 1:
            # noinspection PyUnresolvedReferences
            return super().__getattr__(key)

        key_iter = iter(key_split)
        if (initial := getattr(self, next(key_iter))) is None:
            return

        with suppress(AttributeError):
            return reduce(getattr, key_iter, initial)

    def __setattr__(self, key: str, value: Any) -> None:
        if len(key_split := key.split(".")) == 1:
            return super().__setattr__(key, value)

        if (item := getattr(self, ".".join(key_split[:-1]))) is None:
            raise MyTunesAttributeError(f"Item not found for setting attribute: {key}")
        setattr(item, key_split[-1], value)
