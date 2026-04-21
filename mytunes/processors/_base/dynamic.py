from contextlib import suppress
from functools import partial, update_wrapper, cached_property
from types import NoneType
from typing import Optional, Callable, Any, cast, Self

from mytunes._types import get_base_types
from mytunes.exception import MyTunesValidationError, ModelError
from mytunes.processors._base import Processor
from pydantic import ConfigDict, model_validator
from pydantic.dataclasses import dataclass

from ..._base import ModelMetaclass
from ..._base.attribute import Attribute


# noinspection PyPep8Naming
class processormethod:
    """
    Decorator for methods in a dynamic processor.

    This assigns the method as a processor method which can be dynamically called by the processor class.
    Optionally, provide a list of alternative names via which this processor method can also be called.
    """

    def __new__(cls, *args, **kwargs):
        func: Optional[Callable] = next((arg for arg in args if callable(arg)), None)
        self = partial(cls, *args, **kwargs) if func is None else super().__new__(cls)
        return update_wrapper(self, func)

    def __init__(self, *args: str | Callable):
        self.func = next((arg for arg in args if callable(arg)), None)
        self.alternative_names = tuple(arg for arg in args if isinstance(arg, str))
        self.instance_ = None

    def __get__(self, instance, owner):
        self.instance_ = instance
        return self

    def __call__(self, *args, **kwargs) -> Any:
        return self.func(self.instance_, *args, **kwargs) if self.instance_ else self.func(*args, **kwargs)


@dataclass(config=ConfigDict(frozen=True))
class ProcessorAttribute(Attribute):
    """Assigns the processor attribute to a field via the field's metadata."""
    cleaner: Callable[[str], str] = lambda x: x


class DynamicProcessorMetaclass(ModelMetaclass):
    """
    Metaclass for creating base models which support dynamic processor methods.

    Expands on base model metaclass to add support for:
    - Storing a map of processor method names to their corresponding method on the class, including alternative names.
    - Validation of the processor method name to be called when calling the processor.
    - Calling a processor method on the class based on a given processor method name.
    """
    def __new__(mcs, cls_name: str, bases: tuple[type[Any], ...], namespace: dict[str, Any], **kwargs: Any):
        cls = cast('type[DynamicProcessor]', super().__new__(mcs, cls_name, bases, namespace, **kwargs))

        if (key := "__processor_method_map__") in namespace:
            raise ModelError(f"Cannot define {key} on {cls.__name__!r} as it is a reserved name.")
        cls.__processor_method_map__ = mcs._get_processor_methods(namespace, cls.get_clean_processor_name)

        metadata_fields = cls._metadata_fields
        processor_fields: dict[str, tuple[Any, list[ProcessorAttribute]]] = mcs._get_processor_fields(metadata_fields)
        if cls.__final__:
            mcs._validate_processor_attribute(cls.__name__, processor_fields)

        return cls

    @staticmethod
    def _get_processor_methods(namespace: dict[str, Any], cleaner: Callable[[str], str]) -> dict[str, str]:
        methods: dict[str, str] = {}

        for method in namespace.values():
            if not isinstance(method, processormethod):
                continue

            methods[cleaner(method.__name__)] = method.__name__
            for name in method.alternative_names:
                methods[cleaner(name)] = method.__name__

        return methods

    @classmethod
    def _get_processor_fields(
            mcs, fields: dict[str, tuple[Any, list[Any]]]
    ) -> dict[str, tuple[Any, list[ProcessorAttribute]]]:
        """The fields on the class which have a ProcessorAttribute in their metadata."""
        return {
            name: (annotation, [meta for meta in metadata if isinstance(meta, ProcessorAttribute)])
            for name, (annotation, metadata) in fields.items()
            if any(isinstance(meta, ProcessorAttribute) for meta in metadata)
        }

    @classmethod
    def _validate_processor_attribute(mcs, name: str, fields: dict[str, tuple[Any, list]]) -> None:
        """Validate that the processor field has valid processor attribute metadata."""
        if len(fields) == 0:
            raise ModelError(
                f"{name!r} must have at least one field with a ProcessorAttribute in its metadata."
            )
        if len(fields) > 1:
            raise ModelError(
                f"{name!r} must have only one field with a ProcessorAttribute in its metadata. "
                f"Found {len(fields)}: {', '.join(fields)}"
            )

        field_name = next(iter(fields.keys()))
        _, metadata = next(iter(fields.values()))
        if len(metadata) != 1:
            raise ModelError(
                f"The processor field {field_name!r} on {name!r} must have exactly one ProcessorAttribute "
                f"in its metadata. Found {len(metadata)}."
            )

    @property
    def processor_field_name(cls) -> str:
        """The processor method name to be used when calling this processor"""
        processor_fields = cls._get_processor_fields(cls._metadata_fields)
        return next(iter(processor_fields.keys()))

    @property
    def processor_attribute(cls) -> ProcessorAttribute:
        """The processor attribute metadata on the processor field to be used when calling this processor"""
        processor_fields = cls._get_processor_fields(cls._metadata_fields)
        _, metadata = next(iter(processor_fields.values()))
        return next(iter(metadata))

    def get_clean_processor_name(cls, value: str | None) -> str:
        """The processor attribute metadata on the processor field to be used when calling this processor"""
        return cls.processor_attribute.cleaner(value) if value else None

    @property
    def processor_required(cls) -> bool:
        """The processor attribute metadata on the processor field to be used when calling this processor"""
        processor_fields = cls._get_processor_fields(cls._metadata_fields)
        annotation, _ = next(iter(processor_fields.values()))
        return NoneType not in get_base_types(annotation, ignore_none=False)


# noinspection PyAbstractClass
class DynamicProcessor(Processor, metaclass=DynamicProcessorMetaclass):
    """
    Base class for implementations with dynamic methods.

    Classes that implement this base class have a ``__processor_method_map__`` class attribute
    which is a mapping of all accepted processor names to the processor methods this class contains.

    Classes that implement this base class must have exactly one field with a ProcessorAttribute in its metadata,
    which is used to determine the processor method to call when calling this processor.
    """
    model_config = ConfigDict(ignored_types=(processormethod,))

    @cached_property
    def _processor_name(self) -> str | None:
        """The cleaned processor name to be used when calling this processor"""
        name: str = type(self).processor_field_name
        attribute: ProcessorAttribute = type(self).processor_attribute
        value: str | None = getattr(self, name)
        return attribute.cleaner(value) if value else None

    @cached_property
    def _processor_method_name(self) -> str | None:
        """The processor method name to be used when calling this processor"""
        return self.__processor_method_map__[self._processor_name]

    @cached_property
    def _processor_method(self) -> processormethod:
        """The processor method to be used when calling this processor"""
        return getattr(self, self._processor_method_name)

    @model_validator(mode="after")
    def _validate_processor(self) -> Self:
        if not type(self).processor_required:
            return self

        processor_name = self._processor_name
        if processor_name is None:
            raise MyTunesValidationError("No processor given.")

        if processor_name not in self.__processor_method_map__:
            raise MyTunesValidationError(
                f"Invalid processor name {processor_name!r}. "
                f"Must be one of: {', '.join(self.__processor_method_map__)}"
            )

        return self

    @model_validator(mode="after")
    def _clear_cache(self) -> Self:
        # clear cached properties when revalidating, suppress if cache not yet set
        with suppress(AttributeError):
            del self._processor_name
        with suppress(AttributeError):
            del self._processor_method_name
        with suppress(AttributeError):
            del self._processor_method

        return self

    @model_validator(mode="after")
    def _map_processor_value(self) -> Any:
        field_name: str = type(self).processor_field_name

        field_value = getattr(self, field_name)
        clean_value = type(self).get_clean_processor_name(field_value)
        if clean_value != field_value:
            self.__dict__[field_name] = clean_value

        return self
