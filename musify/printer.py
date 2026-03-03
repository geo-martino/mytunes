## DEPRECATED

"""
The fundamental core printer classes for the entire package.
"""
import re
from abc import ABCMeta, abstractmethod
from collections.abc import Mapping
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime, date
from pathlib import Path
from typing import Any

from aiorequestful.types import UnitIterable, ImmutableJSON, JSON, JSON_VALUE
from yarl import URL

from musify.types import MusifyEnum
from musify.utils import to_collection


class PrettyPrinter(metaclass=ABCMeta):
    """Generic base class for pretty printing. Classes can inherit this class to gain pretty print functionality."""

    __slots__ = ()

    _upper_key_words = {"id", "uri", "url", "bpm"}
    _max_val_width = 120

    @staticmethod
    def _pascal_to_snake(value: str) -> str:
        """Convert PascalCase to snake_case."""
        value = re.sub(r"([A-Z])", lambda m: f"_{m.group(1).lower()}", value.strip("_ "))
        value = re.sub(r"[_ ]+", "_", value).strip("_ ")
        return value.lower()

    @staticmethod
    def _snake_to_pascal(value: str) -> str:
        """Convert snake_case to PascalCase."""
        value = re.sub(r"_(.)", lambda m: m.group(1).upper(), value.strip().lower())
        return re.sub(r"^(.)", lambda m: m.group(1).upper(), value.strip())

    @abstractmethod
    def as_dict(self) -> dict[str, Any]:
        """
        Return a dictionary representation of the key attributes of this object.

        The results of this function are used to produce the following:
            * A JSON representation of the object when calling :py:func:`json`
            * The string representation of the object when calling str() on the object
            * The representation of the object when calling repr() on the object
        """
        raise NotImplementedError

    def _json_attributes(self):
        return self.as_dict()

    def json(self) -> JSON:
        """Return a dictionary representation of the key attributes of this object that is safe to output to JSON"""
        return self._to_json(self._json_attributes())

    @classmethod
    def _to_json(cls, attributes: ImmutableJSON, pool: bool = False) -> JSON:
        def _get_json_key_value(attribute: tuple[Any, Any]) -> tuple[str, JSON_VALUE | list[Future[JSON_VALUE]]]:
            key, value = attribute
            return str(key), cls._get_json_value(value=value)

        if not pool:
            tasks = map(_get_json_key_value, attributes.items())
        else:
            with ThreadPoolExecutor(thread_name_prefix="to-json") as executor:
                tasks = executor.map(_get_json_key_value, attributes.items())

        return dict(tasks)

    @classmethod
    def _get_json_value(cls, value: Any, pool: bool = False) -> JSON_VALUE | list[Future[JSON_VALUE]]:
        if isinstance(value, set):
            value = to_collection(value)

        if isinstance(value, (list, tuple)):
            if not pool:
                tasks = map(cls._get_json_value, value)
            else:
                with ThreadPoolExecutor(thread_name_prefix="to-json-value") as executor:
                    tasks = executor.map(cls._get_json_value, value)
            return list(tasks)
        elif isinstance(value, Mapping):
            return cls._to_json(value, pool=pool)
        elif isinstance(value, PrettyPrinter):
            return value._to_json(value._json_attributes(), pool=pool)
        elif isinstance(value, MusifyEnum):
            return value.name.lower()
        elif isinstance(value, (datetime, date, Path, URL)):
            return str(value)

        return value

    def __str__(self, indent: int = 2, increment: int = 2):
        obj_dict = self.as_dict()
        if not obj_dict:
            return f"{self.__class__.__name__}()"

        result = f"{self.__class__.__name__}(\n{{}}\n" + " " * (indent - increment) + ")"
        attributes_repr = self._to_str(obj_dict, indent=indent, increment=increment)
        return result.format("\n".join([" " * indent + attribute for attribute in attributes_repr]))

    @classmethod
    def _to_str(cls, attributes: Mapping[str, Any], indent: int = 2, increment: int = 2) -> list[str]:
        if len(attributes) == 0:
            return []
        max_key_width = max(map(len, map(str, attributes))) + 1  # +1 for space after key
        max_key_width += max_key_width % increment
        max_val_width = cls._max_val_width - max_key_width

        indent_prev = indent
        indent += increment

        attributes_repr: list[str] = []
        for attr_key, attr_val in attributes.items():
            attr_key = str(attr_key).title().replace('_', ' ')
            for word in cls._upper_key_words:
                pattern = re.compile(rf"(^{word}$|^{word} | {word}$| {word})", flags=re.I)
                attr_key = re.sub(pattern, lambda m: m.group(1).upper(), attr_key)

            if isinstance(attr_val, PrettyPrinter):
                attr_val_str = attr_val.__str__(indent=indent, increment=increment)
            elif isinstance(attr_val, (datetime, date)):
                attr_val_str = str(attr_val)
            elif isinstance(attr_val, (list, tuple, set)) and len(attr_val) > 0:
                attr_val_str = cls._get_attribute_value_from_collection(
                    attr_val=attr_val,
                    max_val_width=max_val_width,
                    indent=indent,
                    indent_prev=indent_prev,
                    increment=increment
                )
            elif isinstance(attr_val, Mapping) and len(attr_val) > 0:
                attr_val_str = cls._get_attribute_value_from_mapping(
                    attr_val=attr_val,
                    max_val_width=max_val_width,
                    indent=indent,
                    indent_prev=indent_prev,
                    increment=increment
                )
            else:
                attr_val_str = repr(attr_val)

            attr_val_repr = f"{attr_key} = {attr_val_str}"  # for single line format
            if len(attr_val_repr) > max_val_width or len(attributes) > 1:
                # reformat to indented list format
                attr_val_repr = f"{attr_key: <{max_key_width}}= {attr_val_str}"
            attributes_repr.append(attr_val_repr)

        return attributes_repr

    @staticmethod
    def _get_attribute_value_from_collection(
            attr_val: list | tuple | set, max_val_width: int, indent: int, indent_prev: int, increment: int
    ) -> str:
        pp_repr = "[{}]"
        if isinstance(attr_val, set):
            pp_repr = "{{}}"
        elif isinstance(attr_val, tuple):
            pp_repr = "({})"

        attr_val_str = str(attr_val)

        if len(attr_val_str) > max_val_width:
            pp_repr = pp_repr.format("\n" + " " * indent + "{}\n" + " " * indent_prev)
            attr_val_pp = []
            for val in attr_val:
                if isinstance(val, PrettyPrinter):
                    attr_val_pp.append(val.__str__(indent=indent + increment, increment=increment))
                else:
                    attr_val_pp.append(str(val))
            attr_val_str = pp_repr.format((",\n" + " " * indent).join(attr_val_pp))

        return attr_val_str

    @classmethod
    def _get_attribute_value_from_mapping(
            cls, attr_val: Mapping, max_val_width: int, indent: int, indent_prev: int, increment: int
    ) -> str:
        attr_val_pp = cls._to_str(attr_val, indent=indent, increment=increment)
        attr_val_str = "{" + ", ".join(attr_val_pp) + "}"

        if len(attr_val_str) > max_val_width:
            pp_repr = "\n" + " " * indent + "{}\n" + " " * indent_prev
            attr_val_str = "{" + pp_repr.format((",\n" + " " * indent).join(attr_val_pp)) + "}"

        return attr_val_str

    def __repr__(self):
        return f"{self.__class__.__name__}({repr(self.as_dict())})"


class AttributePrinter(PrettyPrinter):
    """
    Extends the functionality of a :py:class:`PrettyPrinter`.

    Adds functionality to automatically determine the key attributes that represent child objects
    and uses these for printer representations.
    """

    __slots__ = ()
    __attributes_classes__: UnitIterable[type] = ()
    __attributes_ignore__: UnitIterable[str] = ()

    def _get_attributes(self) -> dict[str, Any]:
        """Returns the key attributes of the current instance for pretty printing"""
        def get_settings(kls: type) -> None:
            """Build up classes and exclude keys for getting attributes"""
            if kls != self.__class__ and kls not in classes:
                classes.append(kls)
            if issubclass(kls, AttributePrinter):
                ignore.update(to_collection(kls.__attributes_ignore__))
                for k in to_collection(kls.__attributes_classes__):
                    get_settings(k)

        classes: list[type] = []
        ignore: set[str] = set()
        get_settings(self.__class__)
        classes.insert(1, self.__class__)

        attributes = {}
        for cls in classes:
            attributes |= {
                k: getattr(self, k) for k in cls.__dict__.keys()
                if k not in ignore and isinstance(getattr(cls, k), property) and not k.startswith("_")
            }

        return attributes

    def as_dict(self) -> dict[str, Any]:
        return self._get_attributes()
