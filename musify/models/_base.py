import inspect
from typing import Any, cast, get_origin, Union, Self

from pydantic import BaseModel as PydanticBaseModel, RootModel as PydanticRootModel, \
    ConfigDict, AliasGenerator, AliasChoices, AliasPath
# noinspection PyProtectedMember
from pydantic._internal._model_construction import ModelMetaclass as PydanticModelMetaclass
from pydantic.fields import FieldInfo
from pydantic_core import PydanticUndefined
from typing_inspection.typing_objects import is_annotated

from musify.exception import MusifyImportError
from musify.models.exception import ModelError, MusifyValidationError


class ModelMetaclass(PydanticModelMetaclass):
    """
    Metaclass for creating base models for this package.

    Expands on Pydantic model metaclass to add support for:
    - Keeping a registry of all final subclasses of a model for use in discriminated unions and annotations.
    - Validating that all class variables defined on a final model and its subclasses are set.
    """
    def __new__(mcs, cls_name: str, bases: tuple[type[Any], ...], namespace: dict[str, Any], **kwargs: Any):
        cls = cast('type[BaseModel]', super().__new__(mcs, cls_name, bases, namespace, **kwargs))

        if not hasattr(cls, "__model_registry__"):
            cls.__model_registry__ = set()

        cls.__model_registry__.update(kls for base in bases for kls in getattr(base, "__model_registry__", []))
        cls.__final__ = any((
            getattr(cls, "__final__", False),
            *(getattr(base, "__final__", False) for base in bases)
        ))

        if cls.__final__:
            cls._validate_all_class_vars_set()
            cls.__model_registry__.add(cls)

        return cls

    def _validate_all_class_vars_set(cls) -> None:
        """Validate that all class variables defined on this model and its subclasses are set."""
        kls = cast('type[BaseModel]', cls)
        for name in kls.__class_vars__:
            if not hasattr(cls, name) or isinstance(getattr(kls, name), FieldInfo):
                raise ModelError(f"{kls.__name__} must have a {name!r} class attribute defined.")

    @property
    def required_modules_installed(cls) -> bool:
        """Check if all required modules for this model are installed."""
        kls = cast('type[BaseModel]', cls)
        return all(module is not None for module in kls.__required_modules__.values())

    @property
    def _metadata_fields(cls) -> dict[str, tuple[Any, list[Any]]]:
        """Get all fields and properties with metadata for this model."""
        return {
            **cls._model_fields_with_metadata,
            **cls._computed_fields_with_metadata,
            **cls._properties_with_metadata,
        }

    @property
    def _model_fields_with_metadata(cls) -> dict[str, tuple[Any, list[Any]]]:
        fields = cast('type[BaseModel]', cls).model_fields
        return {
            name: (field_info.annotation, field_info.metadata)
            for name, field_info in fields.items()
            if field_info.metadata
        }

    @property
    def _computed_fields_with_metadata(cls) -> dict[str, tuple[Any, list[Any]]]:
        fields = cast('type[BaseModel]', cls).model_computed_fields
        return {
            name: (field_info.return_type, field_info.return_type.__metadata__)
            for name, field_info in fields.items()
            if is_annotated(get_origin(field_info.return_type))
        }

    @property
    def _properties_with_metadata(cls) -> dict[str, tuple[Any, list[Any]]]:
        properties = {}
        for kls in cls.mro():
            for name, prop in vars(kls).items():
                if name.startswith("_") or not isinstance(prop, property):
                    continue

                annotation = inspect.signature(prop.fget).return_annotation
                if not is_annotated(get_origin(annotation)):
                    continue
                properties[name] = (annotation, annotation.__metadata__)

        return properties

    @property
    def registered_submodels(cls) -> list[Self]:
        """Get the registered classes for all subclasses of this model."""
        if cls.__final__:
            return []
        return [kls for kls in cls.__model_registry__ if issubclass(kls, cls) and kls.required_modules_installed]

    @property
    def annotation(cls) -> Self:
        """Get the annotation for all subclasses of this model"""
        classes = cls.registered_submodels
        return Union[*classes] if classes else cls


class BaseModel(PydanticBaseModel, metaclass=ModelMetaclass):
    """
    A base class for creating models in this package.

    Expands on Pydantic base model to add:
    - Standard configuration for all models in the package.
    - Additional helper methods
    """
    __required_modules__: dict[str, Any] = {}

    model_config = ConfigDict(
        validate_default=True,
        validate_assignment=True,
        validate_by_name=True,
        validate_by_alias=True,
        alias_generator=AliasGenerator(
            validation_alias=lambda name: name.replace("_", "").rstrip("s")
        ),
    )

    def __new__(cls, *args, **kwargs):
        cls._validate_required_modules_installed()

        if inspect.isabstract(cls):  # force abstract classes to throw validation error for pydantic validation
            raise MusifyValidationError(
                f"{cls.__name__} cannot be instantiated directly, must be subclassed with a specific source and type"
            )
        return super().__new__(cls)

    @classmethod
    def _validate_required_modules_installed(cls) -> None:
        if cls.required_modules_installed:
            return
        raise MusifyImportError(f"Cannot use {cls.__name__}. Required modules: {", ".join(cls.__required_modules__)}")

    @classmethod
    def _get_aliases(cls, name: str, with_serialization_alias: bool = False) -> set[str]:
        try:
            field: FieldInfo = cls.model_fields[name]
        except KeyError:  # not a field, must be a property or computed field
            return {name}

        aliases: set[str | None] = {field.alias}
        if cls.model_config["validate_by_name"]:
            aliases.add(name)
        if with_serialization_alias:
            aliases.add(field.serialization_alias)

        match field.validation_alias:
            case str():
                aliases.add(field.validation_alias)
            case AliasChoices():
                aliases.update(al for al in field.validation_alias.choices if isinstance(al, str))

        return {al for al in aliases if al}

    @classmethod
    def _get_value_from_data(cls, data: dict[str, Any], field_name: str) -> Any:
        field: FieldInfo = cls.model_fields.get(field_name)
        if field is None:
            field = cls.model_computed_fields.get(field_name)
        if field is None:
            return

        if field.alias is not None and field.alias in data:
            return data[field.alias]

        elif isinstance(field, FieldInfo) and field.validation_alias is not None:
            validation_aliases: list[str | AliasPath] = (
                field.validation_alias.choices
                if isinstance(field.validation_alias, AliasChoices)
                else [field.validation_alias]
            )

            for alias in validation_aliases:
                if isinstance(alias, str) and alias in data:
                    return data[alias]
                elif isinstance(alias, AliasPath):
                    value = alias.search_dict_for_path(data)
                    if value is not PydanticUndefined:
                        return value

        if field_name in data:
            return data[field_name]

        if isinstance(field, FieldInfo) and not field.is_required():
            return field.get_default(call_default_factory=True, validated_data=data)


class RootModel[T](PydanticRootModel[T], BaseModel, metaclass=ModelMetaclass):
    pass
