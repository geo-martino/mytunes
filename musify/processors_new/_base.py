"""
Base classes for all processors in this module. Also contains decorators for use in implementations.
"""
import os
import textwrap
from abc import ABCMeta, abstractmethod
from collections.abc import Callable, MutableSequence, Mapping
from functools import partial, update_wrapper
from typing import Any, Optional, Literal, Self

from pydantic import ConfigDict, model_validator, TypeAdapter, PrivateAttr
from tabulate import tabulate
from termcolor import colored

from musify.exception import MusifyValueError
from musify.models import MusifyModel
from musify.models.properties.logger import HasLogger
from musify.utils import get_user_input


class Result(MusifyModel):
    """Stores the results of an operation"""
    model_config = ConfigDict(frozen=True)


class Processor(MusifyModel):
    """Generic base class for processors"""
    pass


# noinspection PyPep8Naming,SpellCheckingInspection
class dynamicprocessormethod:
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


# noinspection SpellCheckingInspection
class DynamicProcessor(Processor, metaclass=ABCMeta):
    """
    Base class for implementations with :py:func:`dynamicprocessormethod` methods.

    Classes that implement this base class have a ``__processormethods__`` class attribute
    which is a list of strings of all the processor methods this class contains.
    If a :py:func:`dynamicprocessormethod` has alternative method names, these names will be added
    to the class' ``__dict__`` as callable methods which point to the decorated method.

    Optionally, you may also define a ``_processor_method_fmt`` class method which
    applies some transformation to all method names.
    The transformed method name is then appended to the class' ``__dict__``.
    The transformation is always applied before extending the class with any given
    alternative method names.
    """
    model_config = ConfigDict(ignored_types=(dynamicprocessormethod,))

    #: The set of processor methods on this processor and any alternative names for them.
    __processor_method_map__: dict[str, str] = {}
    _processor_required: bool = PrivateAttr(default=True)  # whether a processor method is required or not

    @staticmethod
    def _clean_processor_name(name: str) -> str:
        return name

    def __new__(cls, *_, **__):
        for method in cls.__dict__.copy().values():
            if not isinstance(method, dynamicprocessormethod):
                continue

            cls.__processor_method_map__[cls._clean_processor_name(method.__name__)] = method.__name__
            for name in method.alternative_names:
                cls.__processor_method_map__[cls._clean_processor_name(name)] = method.__name__

        return super().__new__(cls)

    @property
    @abstractmethod
    def _processor_name(self) -> str | None:
        """The processor method name to be used when calling this processor"""
        raise NotImplementedError

    @property
    def _processor_method(self) -> Callable:
        """The processor method to be used when calling this processor"""
        processor_name = self._clean_processor_name(self._processor_name)
        method_name = self.__processor_method_map__[processor_name]
        return getattr(self, method_name)

    @model_validator(mode="after")
    def _validate_processor(self) -> Self:
        processor_name = self._clean_processor_name(self._processor_name)
        if self._processor_name is None:
            if not self._processor_required:
                return self
            raise MusifyValueError(f"No processor given.")

        TypeAdapter(Literal[*list(self.__processor_method_map__)]).validate_python(processor_name)
        return self

    def __call__(self, *args, **kwargs) -> Any:
        """Run the dynamic processor"""
        return self._processor_method(*args, **kwargs)


class InputProcessor(Processor, HasLogger, metaclass=ABCMeta):
    """
    Processor that gets user input as part of it processing.

    Contains methods for getting user input and printing formatted options text to the terminal.
    """

    def _get_user_input(self, text: str | None = None) -> str:
        """Print dialog with optional text and get the user's input."""
        inp = get_user_input(text)
        self.logger.debug(f"User input: {inp}")
        return inp.strip()

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

        header = "\n".join(textwrap.wrap(header, cols)) + "\n\n"
        sub_header = colored("Enter one of the following", "cyan") + ":\n"
        log = header + sub_header + tabulate(
            rows,
            tablefmt="plain",
            colalign=("left", "left"),
        )

        return log
