from collections.abc import Hashable
from functools import cached_property
from typing import Any, cast, ClassVar

from pydantic import Field, ConfigDict
from pydantic.dataclasses import dataclass

from mytunes._base.attribute import Attribute
from mytunes.exception import ModelError
from mytunes._base._base import ModelMetaclass, BaseModel


@dataclass(config=ConfigDict(frozen=True))
class UniqueAttribute(Attribute):
    """Metadata for a field that can identify the uniqueness of a model."""


class ResourceMetaclass(ModelMetaclass):
    """
    Metaclass for creating resource models for this package.

    Expands on base model metaclass to add support for:
    - Updating the discriminated union annotation to use the `type` field as a discriminator for subclasses.
    - Merging the configured unique attributes from all subclasses.
    """

    def __new__(mcs, cls_name: str, bases: tuple[type[Any], ...], namespace: dict[str, Any], **kwargs: Any):
        cls = cast('type[ResourceModel]', super().__new__(mcs, cls_name, bases, namespace, **kwargs))

        metadata_fields = cls._metadata_fields

        if (key := "__unique_attributes__") in namespace:
            raise ModelError(f"Cannot define {key} on {cls.__name__!r} as it is a reserved name.")
        cls.__unique_attributes__ = frozenset(mcs._get_unique_fields(metadata_fields))

        return cls

    @classmethod
    def _get_unique_fields(mcs, fields: dict[str, tuple[Any, list[Any]]]) -> set[str]:
        unique_fields = set()
        for field_name, (_, metadata) in fields.items():
            if any(isinstance(meta, UniqueAttribute) for meta in metadata):
                unique_fields.add(field_name)
        return unique_fields

    # @property
    # def annotation(cls) -> Self:
    #     if not cls.registered_submodels:
    #         return cls
    #     return Annotated[
    #         super().annotation,
    #         Field(discriminator="type"),
    #     ]


class ResourceModel(BaseModel, metaclass=ResourceMetaclass):
    """
    A base class for creating resource models in this package.

    Expands on the base model to add support for:
    - The `type` field which can be used as a discriminator for subclasses in the discriminated union annotation.
    - Returning field values which correspond to the unique keys of the resource.
    - Equality comparison of models based on their unique keys.
    """
    type: ClassVar[str] = Field(description="The type of resource this is.")

    @cached_property
    def unique_keys(self) -> set[Hashable]:
        """Get the keys to match on from the matchable attributes of this models"""
        values = {getattr(self, key) for key in self.__unique_attributes__}
        if None in values:
            values.remove(None)

        # also always allow matching on the string representation of the key
        values.update({str(value) for value in values})
        # allow matching identifiers
        values.add(id(self))

        return values

    def __setattr__(self, key: str, value: Any) -> None:
        """Set the value of a given attribute key"""
        super().__setattr__(key, value)
        if key in self.__unique_attributes__ and hasattr(self, "unique_keys"):
            del self.unique_keys  # clear the cached property

    def __eq__(self, other):
        if not isinstance(other, ResourceModel):
            return super().__eq__(other)
        return self.unique_keys == other.unique_keys
