from abc import abstractmethod
from collections.abc import Hashable, Iterable, Collection
from enum import IntEnum
from functools import cached_property, reduce
from typing import Any, ClassVar, Self, get_type_hints, Union, cast, Annotated

from pydantic import BaseModel, RootModel, Field, ConfigDict, TypeAdapter, AliasGenerator, AliasChoices, \
    GetCoreSchemaHandler, GetJsonSchemaHandler
# noinspection PyProtectedMember
from pydantic._internal._model_construction import ModelMetaclass
from pydantic.alias_generators import to_snake
from pydantic.fields import FieldInfo
from pydantic.json_schema import JsonSchemaValue
from pydantic_core import core_schema, CoreSchema

from musify.exception import MusifyValueError, MusifyAttributeError
from musify.utils import get_base_types


def abstract_property() -> property:
    """Create a new abstract property for an attribute."""
    # noinspection PyUnusedLocal
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


class MusifyModelMetaclass(ModelMetaclass):
    """Metaclass for attribute models to handle tag attribute generation and configuration."""

    def __new__(mcs, cls_name: str, bases: tuple[type[Any], ...], namespace: dict[str, Any], **kwargs: Any):
        cls = cast('type[MusifyModel]', super().__new__(mcs, cls_name, bases, namespace, **kwargs))

        if not hasattr(cls, "__model_registry__"):
            cls.__model_registry__ = set()

        cls.__model_registry__.update(kls for base in bases for kls in getattr(base, "__model_registry__", []))
        cls.__final__ = any((
            getattr(cls, "__final__", False),
            *(getattr(base, "__final__", False) for base in bases)
        ))

        if cls.__final__:
            cls.__model_registry__.add(cls)

        if cls.__final__:
            cls._validate_all_class_vars_set()

        return cls

    def _validate_all_class_vars_set(cls: MusifyModel) -> None:
        """Validate that all class variables defined on this model and its subclasses are set."""
        for name in cls.__class_vars__:
            if not hasattr(cls, name) or isinstance(getattr(cls, name), FieldInfo):
                raise MusifyAttributeError(f"{cls.__name__} must have a {name!r} class attribute defined.")

    @property
    def registered_submodels[T: MusifyModel](cls: type[T]) -> set[type[T]]:
        """Get the registered classes for all subclasses of this model."""
        if cls.__final__:
            return set()
        return {kls for kls in cls.__model_registry__ if issubclass(kls, cls)}

    @property
    def annotation[T: MusifyModel](cls: type[T]) -> type[T]:
        """Get the annotation for all subclasses of this model"""
        classes = cls.registered_submodels
        return Union[*classes] if classes else cls


class MusifyModel(BaseModel, metaclass=MusifyModelMetaclass):
    """Generic base class for any Musify models."""

    model_config = ConfigDict(
        validate_default=True,
        validate_assignment=True,
        validate_by_name=True,
        validate_by_alias=True,
        alias_generator=AliasGenerator(
            validation_alias=lambda name: name.replace("_", "").rstrip("s")
        ),
    )

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


class MusifyRootModel[T](RootModel[T], MusifyModel):
    pass


class MusifyResourceMetaclass(MusifyModelMetaclass):
    """Metaclass for resource models to handle unique attribute generation and configuration."""

    def __new__(mcs, cls_name: str, bases: tuple[type[Any], ...], namespace: dict[str, Any], **kwargs: Any):
        cls = cast('type[MusifyResource]', super().__new__(mcs, cls_name, bases, namespace, **kwargs))

        cls.__unique_attributes__ = frozenset({
            *getattr(cls, "__unique_attributes__", []),
            *(attr for base in bases for attr in getattr(base, "__unique_attributes__", []))
        })

        return cls

    @property
    def annotation[T: MusifyResource](cls: type[T]) -> type[T]:
        if not cls.registered_submodels:
            return cls
        return Annotated[
            super().annotation,
            Field(discriminator="type"),
        ]


class MusifyResource(MusifyModel, metaclass=MusifyResourceMetaclass):
    """Generic class for storing attributes relating to some resource."""

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

    def __eq__(self, other):
        if not isinstance(other, MusifyResource):
            return super().__eq__(other)
        return self.unique_keys == other.unique_keys
    #
    # def __setattr__(self, key: str, value: Any) -> None:
    #     """Set the value of a given attribute key"""
    #     super().__setattr__(key, value)
    #     if key in self.__unique_attributes__ and hasattr(self, "unique_keys"):
    #         del self.unique_keys  # clear the cached property


class AttributeModelMetaclass(MusifyModelMetaclass):
    """Metaclass for attribute models to handle tag attribute generation and configuration."""

    def __new__(mcs, cls_name: str, bases: tuple[type[Any], ...], namespace: dict[str, Any], **kwargs: Any):
        cls = cast('type[AttributeResource]', super().__new__(mcs, cls_name, bases, namespace, **kwargs))

        cls.__include_fields__ = any((
            getattr(cls, "__include_fields__", False),
            *(getattr(base, "__include_fields__", False) for base in bases)
        ))
        cls.__include_properties__ = any((
            getattr(cls, "__include_properties__", False),
            *(getattr(base, "__include_properties__", False) for base in bases)
        ))

        if "__tag_attributes__" not in namespace:
            attribute_names = []
            if cls.__include_fields__:
                keys = cls.__annotations__.keys() - cls.__class_vars__  # exclude class vars
                attribute_names.extend(name for name in keys if not name.startswith("_"))
            if cls.__include_properties__:
                attribute_names.extend(name for name, method in namespace.items() if isinstance(method, property))

            cls.__tag_attributes__ = tuple(attribute_names)

        cls.__tag_attributes__ = tuple(cls._get_tag_attributes(cls.__tag_attributes__))

        return cls

    def _get_tag_attributes(cls: AttributeModel, attributes: Iterable[str]) -> tuple[str]:
        attribute_names = []
        for attr in attributes:
            names = cls._get_nested_tag_attributes(attr) + cls._get_parent_tag_attributes()
            attribute_names.extend(attr for attr in names if attr not in attribute_names)

        return tuple(attribute_names)

    def _get_nested_tag_attributes(cls: AttributeModel, name: str) -> list[str]:
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

    def _get_attribute_annotation(cls: AttributeModel, name: str) -> type:
        field: FieldInfo | None = cls.model_fields.get(name)
        if field is not None:
            annotation = field.annotation
        elif isinstance(field := cls.get_nested_field_info(name), FieldInfo):
            annotation = field.annotation
        elif isinstance(field, property):
            try:
                annotation = get_type_hints(field.fget, include_extras=True)["return"]
            except NameError:  # Forward reference not resolved
                annotation = Any
        else:
            annotation = type(field)

        return annotation

    def _get_parent_tag_attributes(cls: AttributeModel) -> list[str]:
        attribute_names = []
        for kls in cls.mro():
            if kls is not cls and kls not in (AttributeModel, AttributeModel) and issubclass(kls, AttributeModel):
                attribute_names.extend(attr for attr in kls.__tag_attributes__ if attr not in attribute_names)

        return attribute_names

    def get_nested_field_info(cls: AttributeModel, key: str) -> FieldInfo:
        """Get field info for a given key, supporting nested keys using dot notation."""
        if len(key_split := key.split(".")) == 1:
            if key in cls.model_fields:
                return cls.model_fields[key]
            return getattr(cls, key)

        key_iter = iter(key_split[:-1])
        field = reduce(
            AttributeModelMetaclass._get_tag_field_from_field_info,
            key_iter,
            AttributeModelMetaclass._get_tag_field_from_field_info(cls, next(key_iter))
        )

        return AttributeModelMetaclass.get_nested_field_info(field, key_split[-1])

    @staticmethod
    def _get_tag_field_from_field_info(cls: AttributeModel, key: str) -> type:
        if key not in cls.model_fields:
            return getattr(cls, key)

        annotation = cls.model_fields[key].annotation
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
            # noinspection PyUnresolvedReferences
            return super().__getattr__(key)

        key_iter = iter(key_split)
        if (initial := getattr(self, next(key_iter))) is None:
            return

        try:
            return reduce(getattr, key_iter, initial)
        except AttributeError:
            return None

    def __setattr__(self, key: str, value: Any) -> None:
        if len(key_split := key.split(".")) == 1:
            return super().__setattr__(key, value)

        if (item := getattr(self, ".".join(key_split[:-1]))) is None:
            raise MusifyAttributeError(f"Item not found for setting attribute: {key}")
        setattr(item, key_split[-1], value)


class AttributeResourceMetaclass(MusifyResourceMetaclass, AttributeModelMetaclass):
    pass


class AttributeResource(AttributeModel, MusifyResource, metaclass=AttributeResourceMetaclass):
    """Defines a common base model for resources made of common attributes."""
    __include_fields__ = True
    __include_properties__ = True


class CollectionModel[IT: MusifyResource](MusifyModel):
    """Defines a common base models for attributes made of common collection properties."""
    @property
    @abstractmethod
    def _items(self) -> Collection:
        """The items in this collection."""
        raise NotImplementedError

    @property
    def items_count(self) -> int:
        """The number of items currently loaded in this collection."""
        return len(self._items)

    @property
    def items_iter(self) -> Iterable[IT]:
        """The number of items currently loaded in this collection."""
        return iter(self._items)


# noinspection PyAbstractClass
class CollectionResource[IT: MusifyResource](CollectionModel[IT], MusifyResource):
    """Defines a common base model for resources made of common collection properties."""


class MusifyEnum(IntEnum):
    """Generic class for :py:class:`IntEnum` implementations for the entire package."""

    # noinspection PyUnusedLocal
    @classmethod
    def __get_pydantic_core_schema__(cls, source: Any, handler: GetCoreSchemaHandler) -> CoreSchema:
        return core_schema.no_info_after_validator_function(
            cls._validate,
            core_schema.union_schema(
                [core_schema.str_schema(), core_schema.int_schema()]
            ),
            serialization=core_schema.plain_serializer_function_ser_schema(lambda x: x.name),
        )

    # noinspection PyUnusedLocal
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
