import itertools
from abc import abstractmethod
from collections.abc import Hashable, Iterable
from enum import IntEnum
from functools import cached_property, reduce
from typing import Any, ClassVar, Self, get_type_hints, get_origin, get_args

from pydantic import BaseModel, RootModel, Field, ConfigDict, TypeAdapter, AliasGenerator, AliasChoices, \
    GetCoreSchemaHandler, GetJsonSchemaHandler
from pydantic._internal._generics import PydanticGenericMetadata
from pydantic._internal._model_construction import ModelMetaclass
from pydantic.alias_generators import to_snake
from pydantic.fields import FieldInfo
from pydantic.json_schema import JsonSchemaValue
from pydantic_core import core_schema, CoreSchema

from musify.exception import MusifyValueError, MusifyTypeError
from musify.utils import classproperty, get_base_types


def abstract_property() -> property:
    """Create a new abstract property for an attribute."""

    def fget(self) -> Any:
        raise NotImplementedError

    return property(abstractmethod(fget))


def readable_computed_field(name: str) -> property:
    """Create a new readable computed_field for an attribute with the given ``name``."""
    name = f"__{name.lstrip("_")}"

    def fget(self) -> Any:
        field = self.model_computed_fields[name.lstrip("_")]
        value = getattr(self, name, None)
        TypeAdapter(field.return_type).validate_python(value)  # validate return
        return value

    return property(fget)


def writeable_computed_field(name: str) -> property:
    """Create a new writeable computed_field for an attribute with the given ``name``."""
    name = f"__{name.lstrip("_")}"

    def fget(self) -> Any:
        field = self.__class__.model_computed_fields[name.lstrip("_")]
        value = getattr(self, name, None)
        TypeAdapter(field.return_type).validate_python(value)  # validate return
        return value

    def fset(self, value) -> None:
        field = self.__class__.model_computed_fields[name.lstrip("_")]
        value = TypeAdapter(field.return_type).validate_python(value)
        setattr(self, name, value)

    def fdel(self) -> None:
        delattr(self, name)

    return property(fget, fset, fdel)


class MusifyModel(BaseModel):
    """Generic base class for any Musify models."""
    model_config = ConfigDict(
        validate_default=True,
        validate_assignment=True,
        validate_by_name=True,
        validate_by_alias=True,
        alias_generator=AliasGenerator(
            validation_alias=lambda name: name.replace("_", "").rstrip("s")
        )
    )

    # TODO: figure this out
    # _clean_tags: dict[TagField, Any] = PrivateAttr(
    #     # description="A map of tags that have been cleaned to use when matching/searching",
    #     default_factory=dict,
    # )

    def __init__(self, **kwargs):
        # Allow setting writeable computed fields on init
        computed_field_values = {}
        for field in self.__class__.model_computed_fields.keys():
            if field in self.__class__.model_fields or kwargs.get(field) is None:
                continue

            attr = getattr(self.__class__, field)
            if attr.fset is not None:
                computed_field_values[field] = kwargs.pop(field)
            elif any(
                    name.endswith(field_private := f"_{field}")
                    for name in getattr(self.__class__, "__private_attributes__", ())
            ):
                computed_field_values[field_private] = kwargs.pop(field)

        super().__init__(**kwargs)
        for field, value in computed_field_values.items():
            setattr(self, field, value)

    @classmethod
    def _get_aliases(cls, name: str) -> set[str]:
        try:
            field: FieldInfo = cls.model_fields[name]
        except KeyError:  # not a field, must be a property or computed field
            return {name}

        aliases = {name, field.serialization_alias, field.alias}
        if isinstance(field.validation_alias, str):
            aliases.add(field.validation_alias)
        elif isinstance(field.validation_alias, AliasChoices):
            aliases |= set(al for al in field.validation_alias.choices if isinstance(al, str))

        return {al for al in aliases if al}


class MusifyRootModel[T](RootModel[T]):
    model_config = ConfigDict(
        validate_default=True,
        validate_assignment=True,
        validate_by_name=True,
        validate_by_alias=True,
    )


class MusifyResource(MusifyModel):
    """Generic class for storing attributes relating to some resource."""
    __unique_attributes__: ClassVar[frozenset[str]] = frozenset()

    type: ClassVar[str] = Field(description="The type of resource this is.")

    @cached_property
    def _unique_attribute_keys(self) -> set[str]:
        return {
            key
            for cls in self.__class__.mro() if issubclass(cls, AttributeResource)
            for key in cls.__unique_attributes__
        }

    @cached_property
    def unique_keys(self) -> set[Hashable]:
        """Get the keys to match on from the matchable attributes of this models"""
        values = {getattr(self, key) for key in self._unique_attribute_keys}
        if None in values:
            values.remove(None)

        # also always allow matching on the string representation of the key
        values.update({str(value) for value in values})
        # allow matching identifiers
        values.add(id(self))

        return values

    def __eq__(self, other):
        if not isinstance(other, MusifyResource):
            return super().__eq__(other)
        return self.unique_keys == other.unique_keys

    def __setattr__(self, key: str, value: Any) -> None:
        """Set the value of a given attribute key"""
        super().__setattr__(key, value)
        if key in self._unique_attribute_keys and hasattr(self, "unique_keys"):
            # noinspection PyPropertyAccess
            del self.unique_keys  # clear the cached property


class AttributeModelMetaclass(ModelMetaclass):
    """Metaclass for attribute models to handle tag attribute generation and configuration."""
    __tag_attributes__: ClassVar[frozenset[str] | tuple[str] | None] = None
    __include_fields__: ClassVar[bool] = False
    __include_properties__: ClassVar[bool] = False

    def __new__(
        mcs,
        cls_name: str,
        bases: tuple[type[Any], ...],
        namespace: dict[str, Any],
        __pydantic_generic_metadata__: PydanticGenericMetadata | None = None,
        __pydantic_reset_parent_namespace__: bool = True,
        _create_model_module: str | None = None,
        **kwargs: Any,
    ) -> type:
        # noinspection PyTypeChecker
        cls: MusifyModel = super().__new__(
            mcs,
            cls_name,
            bases,
            namespace,
            __pydantic_generic_metadata__,
            __pydantic_reset_parent_namespace__,
            **kwargs
        )

        if "__tag_attributes__" not in namespace:  # no tag attributes explicitly defined
            cls.__tag_attributes__ = None

        if cls.__tag_attributes__ is None:
            attribute_names = []
            if cls.__include_fields__:
                attribute_names.extend(name for name in cls.__annotations__.keys() if not name.startswith("_"))
            if cls.__include_properties__:
                attribute_names.extend(name for name, method in namespace.items() if isinstance(method, property))

            cls.__tag_attributes__ = tuple(attribute_names)

        cls.__tag_attributes__ = tuple(cls._get_tag_attributes(cls.__tag_attributes__))
        return cls

    def _get_tag_attributes(cls, attributes: Iterable[str]) -> tuple[str]:
        attribute_names = []
        for attr in attributes:
            names = cls._get_nested_tag_attributes(attr) + cls._get_parent_tag_attributes()
            attribute_names.extend(attr for attr in names if attr not in attribute_names)

        return tuple(attribute_names)

    def _get_nested_tag_attributes(cls, name: str) -> list[str]:
        annotation = cls._get_attribute_annotation(name)

        attribute_names = [name]
        for kls in get_base_types(annotation, ignore_none=True, resolve_generics=True):
            if not issubclass(kls, AttributeModel):
                continue

            attribute_names.extend(
                attr_name for attr in kls.__tag_attributes__
                if (attr_name := f"{name}.{attr}") not in attribute_names
            )

        return attribute_names

    def _get_attribute_annotation(cls, name: str) -> type:
        field: FieldInfo | None = cls.model_fields.get(name)
        if field is not None:
            annotation = field.annotation
        elif isinstance(field := getattr(cls, name), FieldInfo):
            annotation = field.annotation
        elif isinstance(field, property):
            try:
                annotation = get_type_hints(field.fget, include_extras=True)["return"]
            except NameError:  # Forward reference not resolved
                annotation = Any
        else:
            annotation = type(field)

        return annotation

    def _get_parent_tag_attributes(cls) -> list[str]:
        attribute_names = []
        for kls in cls.mro():
            if kls is not cls and kls not in (AttributeModel, AttributeModel) and issubclass(kls, AttributeModel):
                attribute_names.extend(attr for attr in kls.__tag_attributes__ if attr not in attribute_names)

        return attribute_names

    def __getattr__(cls, key: str) -> Any:
        if len(key_split := key.split(".")) == 1:
            if key in cls.model_fields:
                return cls.model_fields[key]
            return super().__getattr__(key)

        key_iter = iter(key_split[:-1])
        field = reduce(
            AttributeModelMetaclass._get_tag_field_from_field_info,
            key_iter,
            cls._get_tag_field_from_field_info(cls, next(key_iter))
        )

        return getattr(field, key_split[-1])

    @staticmethod
    def _get_tag_field_from_field_info(cls, key: str) -> type:
        if not isinstance(field := getattr(cls, key), FieldInfo):
            return field

        annotation = field.annotation
        return next(
            (
                arg for arg in get_base_types(annotation, ignore_none=True, resolve_generics=True)
                if issubclass(arg, AttributeModel)
            ),
            annotation
        )


class AttributeModel(MusifyModel, metaclass=AttributeModelMetaclass):
    """
    Attribute model base class to define common attributes for resources.

    Adds support for getting and setting nested attributes using dot notation.
    """
    def __getattr__(self, key: str) -> Any:
        if len(key_split := key.split(".")) == 1:
            return super().__getattr__(key)

        key_iter = iter(key_split)
        return reduce(getattr, key_iter, getattr(self, next(key_iter)))

    def __setattr__(self, key: str, value: Any) -> None:
        if len(key_split := key.split(".")) == 1:
            return super().__setattr__(key, value)

        item = getattr(self, ".".join(key_split[:-1]))
        setattr(item, key_split[-1], value)


class AttributeResource(AttributeModel, MusifyResource):
    """Defines a common base model for resources made of common attributes."""
    __include_fields__ = True
    __include_properties__ = True


class CollectionModel(MusifyModel):
    """Defines a common base models for attributes made of common collection properties."""


class CollectionResource(CollectionModel, MusifyResource):
    """Defines a common base model for resources made of common collection properties."""


class MusifyEnum(IntEnum):
    """Generic class for :py:class:`IntEnum` implementations for the entire package."""

    @classmethod
    def __get_pydantic_core_schema__(cls, source_type: Any, handler: GetCoreSchemaHandler) -> CoreSchema:
        return core_schema.no_info_after_validator_function(
            cls._validate,
            core_schema.union_schema(
                [core_schema.str_schema(), core_schema.int_schema()]
            ),
            serialization=core_schema.plain_serializer_function_ser_schema(lambda x: x.name),
        )

    @classmethod
    def __get_pydantic_json_schema__(cls, schema: CoreSchema, handler: GetJsonSchemaHandler) -> JsonSchemaValue:
        return {'enum': [m.name for m in cls], 'type': 'string'}

    @classmethod
    def _validate(cls, value: Any) -> Self:
        match value:
            case str():
                return cls[to_snake(value).upper()]
            case int():
                return cls(value)
            case _:
                raise MusifyValueError(f"Cannot get enum for {value!r}")
