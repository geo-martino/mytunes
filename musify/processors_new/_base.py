"""
Base classes for all processors in this module. Also contains decorators for use in implementations.
"""
import os
import textwrap
from collections.abc import Callable, Mapping, Iterable
from functools import partial, update_wrapper
from typing import Any, Optional, Self, cast

from pydantic import ConfigDict, model_validator, PrivateAttr
from tabulate import tabulate
from termcolor import colored

from musify.exception import MusifyValueError
from musify.models import BaseModel, abstract_property
from musify.models._base import ModelMetaclass
from musify.models.exception import MusifyValidationError, ModelError
from musify.models.properties.logger import HasLogger
from musify.models.properties.name import HasName
from musify.models.properties.uri import HasImmutableURI, HasMutableURI, item_has_uri


class Processor(BaseModel):
    """Generic base class for processors"""
    @classmethod
    def _format_item_message(
            cls,
            method: str,
            item: Any,
            messages: str | Iterable,
            pad: str = " ",
    ) -> str:
        if isinstance(messages, str):
            messages = (messages,)

        title = cls._get_item_log_value(item)
        header = f"{pad[0] * 3} {method.upper():<7}: {title}"
        return "|" + " | ".join([header] + list(map(str, messages)))

    @staticmethod
    def _get_item_log_value(item: Any) -> str:
        match item:
            case HasImmutableURI() | HasMutableURI() if item_has_uri(item):
                return str(item.uri)
            case HasName():
                return str(item.name)
            case _:
                return "- UNKNOWN -"


# noinspection PyPep8Naming,SpellCheckingInspection
class processor:
    """
    Decorator for methods on a class decorated with the :py:func:`processor` decorator

    This assigns the method a processor method which can be dynamically called by the processor class.
    Optionally, provide a list of alternative names from which this processor method can also be called.
    """

    def __new__(cls, *args, **__):
        func: Optional[Callable] = next((a for a in args if callable(a)), None)
        self = partial(cls, *args) if func is None else super().__new__(cls)
        return update_wrapper(self, func)

    def __init__(self, *args: str | Callable):
        self.func = next((a for a in args if callable(a)), None)
        self.alternative_names = tuple(a for a in args if isinstance(a, str))
        self.instance_ = None

    def __get__(self, instance, owner):
        self.instance_ = instance
        return self

    def __call__(self, *args, **kwargs) -> Any:
        return self.func(self.instance_, *args, **kwargs) if self.instance_ else self.func(*args, **kwargs)


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
        cls.__processor_method_map__ = mcs._get_processor_methods(namespace, cls._clean_processor_name)

        return cls

    @staticmethod
    def _get_processor_methods(namespace: dict[str, Any], cleaner: Callable[[str], str]) -> dict[str, str]:
        methods: dict[str, str] = {}

        for method in namespace.values():
            if not isinstance(method, processor):
                continue

            methods[cleaner(method.__name__)] = method.__name__
            for name in method.alternative_names:
                methods[cleaner(name)] = method.__name__

        return methods


# noinspection SpellCheckingInspection,PyAbstractClass
class DynamicProcessor(Processor, metaclass=DynamicProcessorMetaclass):
    """
    Base class for implementations with :py:func:`processor` decorated methods.

    Classes that implement this base class have a ``__processor_method_map__`` class attribute
    which is a mapping of all accepted processor names to the processor methods this class contains.

    Optionally, you may also define a ``_clean_processor_name`` class method which
    applies some transformation to all method names.
    The transformation is always applied before extending the class with any given
    alternative method names.
    """
    model_config = ConfigDict(ignored_types=(processor,))

    @staticmethod
    def _clean_processor_name(name: str) -> str:
        return name

    @property
    def _processor_name(self) -> str:
        """The processor method name to be used when calling this processor"""
        raise NotImplementedError

    @property
    def _processor_method(self) -> processor:
        """The processor method to be used when calling this processor"""
        processor_name = self._clean_processor_name(self._processor_name)
        method_name = self.__processor_method_map__[processor_name]
        return getattr(self, method_name)

    @model_validator(mode="after")
    def _validate_processor(self) -> Self:
        try:
            processor_name = self._processor_name
        except NotImplementedError:
            return self  # processor not required

        if processor_name is None:
            raise MusifyValidationError("No processor given.")

        clean_processor_name = self._clean_processor_name(processor_name)
        if clean_processor_name not in self.__processor_method_map__:
            raise MusifyValidationError(
                f"Invalid processor name {processor_name!r}. "
                f"Must be one of: {', '.join(self.__processor_method_map__)}"
            )

        return self


class InputProcessor(Processor, HasLogger):
    """
    Processor that gets user input as part of it processing.

    Contains methods for getting user input and printing formatted options text to the terminal.
    """

    def _get_user_input(self, text: str | None = None) -> str:
        """Print dialog with optional text and get the user's input."""
        if not text:
            text = "Enter input"

        log = " ".join((colored(text, "yellow"), colored("|", "white", attrs=["bold"])))
        inp = input(log + " ").strip()

        self.logger.debug(f"User input: {inp}")
        return inp

    @staticmethod
    def _format_help_text(options: Mapping[str, str], header: str | None = None) -> str:
        """Format help text with a given mapping of options. Add an option header to include before options."""
        try:
            cols = os.get_terminal_size().columns
        except OSError:
            cols = 120

        max_key_width = max(len(key) for key in options)

        rows = []
        for key, description in options.items():
            row = (
                colored(key, "blue", attrs=["bold"]) + (":" if description else ""),
                colored("\n".join(textwrap.wrap(description, cols - max_key_width)), "white"),
            )
            rows.append(row)

        header = "\n".join(textwrap.wrap(header, cols)) + "\n\n" if header else ""
        sub_header = colored("Enter one of the following", "cyan") + ":\n"
        log = header + sub_header + tabulate(
            rows,
            tablefmt="plain",
            colalign=("left", "left"),
        )

        return log
