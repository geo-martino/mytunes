from collections.abc import MutableMapping
from typing import Any, cast, get_args, Self, Annotated

from pydantic import Field, ConfigDict, model_validator
from pydantic.dataclasses import dataclass
from pydantic.fields import FieldInfo

from mytunes._base._base import ModelMetaclass, BaseModel
from mytunes._base.attribute import Attribute
from mytunes.exception import ModelError
from mytunes.logger import Logger


@dataclass(config=ConfigDict(frozen=True))
class DiscriminatorAttribute(Attribute):
    """Metadata for a field that can identify the discriminator field."""


class DiscriminatorMetaclass(ModelMetaclass):
    """
    Metaclass for creating models to be used in discriminated unions by field value.

    Expands on base model metaclass to add support for:
    - Updating the discriminated union annotation to use the appropriate annotated field
      as a discriminator for subclasses.
    """

    def __new__(mcs, cls_name: str, bases: tuple[type[Any], ...], namespace: dict[str, Any], **kwargs: Any):
        cls = cast('type[DiscriminatorModel]', super().__new__(mcs, cls_name, bases, namespace, **kwargs))

        metadata_fields = cls._metadata_fields

        if (key := "__discriminator_field__") in namespace:
            raise ModelError(f"Cannot define {key} on {cls.__name__!r} as it is a reserved name.")
        cls.__discriminator_field__ = mcs._get_discriminator_field(metadata_fields)

        return cls

    @classmethod
    def _get_discriminator_field(mcs, fields: dict[str, tuple[Any, list[Any]]]) -> str | None:
        discriminator_fields = set()
        for field_name, (_, metadata) in fields.items():
            if any(isinstance(meta, DiscriminatorAttribute) for meta in metadata):
                discriminator_fields.add(field_name)

        if len(discriminator_fields) > 1:
            log_fields = Logger.format_list_to_string(sorted(discriminator_fields))
            raise ModelError(f"Too many discriminator fields defined: {log_fields}")

        return next(iter(discriminator_fields), None)

    @property
    def annotation(cls) -> Self:
        if not cls.registered_submodels:
            return cls
        if not cls.__discriminator_field__:
            raise ModelError(f"Cannot generated annotation for {cls.__name__!r}: no discriminator field defined.")

        return Annotated[
            super().annotation,
            Field(discriminator=cls.__discriminator_field__)
        ]


class DiscriminatorModel(BaseModel, metaclass=DiscriminatorMetaclass):
    """
    A base class for creating models with discriminated unions in this package.

    Expands on the base model to add support for:
    - Using the annotated discriminated field for subclasses in the discriminated union annotation.
    - Automatically setting the value of discriminated field when initialised directly.
    """
    __final__ = False

    @model_validator(mode="before")
    @classmethod
    def _add_discriminator_value[T](cls, data: T | MutableMapping[str, Any]) -> T | MutableMapping[str, Any]:
        """This should only be called when calling the model directly, not on union validation."""
        if not isinstance(data, MutableMapping) or not cls.__final__ or not (key := cls.__discriminator_field__):
            return data

        field: FieldInfo = cls.model_fields[key]
        if not field.is_required() or cls._get_value_from_data(data, key) is not None:
            return data

        discriminator_type = field.annotation
        discriminator_value = next(iter(get_args(discriminator_type)))
        data[key] = discriminator_value

        return data
