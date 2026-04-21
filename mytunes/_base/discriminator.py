from collections.abc import Hashable
from functools import cached_property
from typing import Any, cast, ClassVar, get_args, Self, Annotated

from pydantic import Field, ConfigDict
from pydantic.dataclasses import dataclass

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

    def __init__(self, /, **data: Any) -> None:
        if self.__final__:
            discriminator_type = type(self).model_fields[self.__discriminator_field__].annotation
            discriminator_value = next(iter(get_args(discriminator_type)))
            data[self.__discriminator_field__] = discriminator_value

        super().__init__(**data)
