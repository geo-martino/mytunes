from annotationlib import ForwardRef
from collections.abc import Iterable, Mapping, Iterator
from types import UnionType, GenericAlias
from typing import Annotated, Any, TypeAliasType, get_args, evaluate_forward_ref, Union, TypeVar

from annotated_types import MinLen
from pydantic import StringConstraints, BeforeValidator, BaseModel, GetCoreSchemaHandler, GetJsonSchemaHandler
from pydantic.alias_generators import to_snake
from pydantic.json_schema import JsonSchemaValue
from pydantic_core import PydanticUseDefault, CoreSchema, core_schema
from typing_extensions import get_origin
from typing_inspection.typing_objects import is_annotated, is_typevar
from yarl import URL as YARL_URL

from mytunes.exception import MyTunesTypeError

###########################################################################
## Basic annotations
###########################################################################
type Character = Annotated[str, StringConstraints(min_length=1, max_length=1)]
type StrippedCharacter = Annotated[str, StringConstraints(min_length=1, max_length=1, strip_whitespace=True)]
type String = Annotated[str, StringConstraints(min_length=1)]
type StrippedString = Annotated[str, StringConstraints(min_length=1, strip_whitespace=True)]
type LowerStrippedString = Annotated[str, StringConstraints(min_length=1, strip_whitespace=True, to_lower=True)]
type UpperStrippedString = Annotated[str, StringConstraints(min_length=1, strip_whitespace=True, to_upper=True)]
type LowerSnakeCase = Annotated[
    str,
    StringConstraints(min_length=1, strip_whitespace=True, to_lower=True),
    BeforeValidator(to_snake),
]
type UpperSnakeCase = Annotated[
    str,
    StringConstraints(min_length=1, strip_whitespace=True, to_upper=True),
    BeforeValidator(to_snake),
]
type ListWithValues[T] = Annotated[list[T], MinLen(1)]

type Number = int | float


###########################################################################
## Validators
###########################################################################
def to_set(value: Any) -> set[Any] | None:
    """Converts a value to a set."""
    match value:
        case None:
            return
        case str() | Mapping() | BaseModel():
            return {value}
        case Iterable():
            return set(value)
        case _:
            return {value}


TO_SET = BeforeValidator(to_set)


def to_tuple(value: Any) -> tuple[Any] | None:
    """Converts a value to a tuple."""
    match value:
        case None:
            return
        case str() | Mapping() | BaseModel():
            return (value,)
        case Iterable():
            return tuple(value)
        case _:
            return (value,)


TO_TUPLE = BeforeValidator(to_tuple)


def to_list(value: Any) -> list[Any] | None:
    """Converts a value to a list."""
    match value:
        case None:
            return
        case str() | Mapping() | BaseModel():
            return [value]
        case Iterable():
            return list(value)
        case _:
            return [value]


TO_LIST = BeforeValidator(to_list)


def _default_if_none[T](value: T) -> T:
    """Use the Pydantic default if value is None."""
    if value is None:
        raise PydanticUseDefault()
    return value


DEFAULT_IF_NONE = BeforeValidator(_default_if_none)


###########################################################################
## 3rd party models
###########################################################################
class _URLSchema:
    # noinspection PyUnusedLocal
    @classmethod
    def __get_pydantic_core_schema__(cls, source: Any, handler: GetCoreSchemaHandler) -> CoreSchema:
        url_schema = core_schema.url_schema(host_required=True)
        cast_str_schema = core_schema.chain_schema(
            [
                url_schema,
                core_schema.no_info_plain_validator_function(lambda x: YARL_URL(str(x))),
            ]
        )
        python_schema = core_schema.union_schema(
            [
                core_schema.is_instance_schema(YARL_URL),
                cast_str_schema,
            ]
        )

        return core_schema.json_or_python_schema(
            json_schema=url_schema,
            python_schema=python_schema,
            serialization=core_schema.to_string_ser_schema()
        )

    @classmethod
    def __get_pydantic_json_schema__(
        cls, _core_schema: CoreSchema, handler: GetJsonSchemaHandler
    ) -> JsonSchemaValue:
        return handler(core_schema.url_schema())


HttpURL = Annotated[
    YARL_URL, _URLSchema
]


###########################################################################
## Utilities
###########################################################################
def get_base_types(
        annotation: type | UnionType | GenericAlias | TypeAliasType,
        ignore_none: bool = True,
        resolve_generics: bool = False,
) -> tuple[type, ...]:
    """
    Get all base types for a given type annotation.

    :param annotation: The type annotation to get the base types for.
    :param ignore_none: Whether to drop NoneType base types.
    :param resolve_generics: Whether to resolve TypeVars to their constraints or bounds.
    :return: A tuple of all base types.
    """
    bases = []
    match annotation:
        case UnionType():
            for kls in get_args(annotation):
                bases.extend(get_base_types(kls, ignore_none=ignore_none, resolve_generics=resolve_generics))
        case GenericAlias():
            bases.append(get_origin(annotation))
        case ForwardRef():
            annotation = evaluate_forward_ref(annotation)
            bases.extend(get_base_types(annotation, ignore_none=ignore_none, resolve_generics=resolve_generics))
        case TypeAliasType():
            ano = annotation.__value__
            bases.extend(get_base_types(ano, ignore_none=ignore_none, resolve_generics=resolve_generics))
        case _ if is_annotated(get_origin(annotation)):
            # noinspection PyUnresolvedReferences
            ano = annotation.__origin__
            bases.extend(get_base_types(ano, ignore_none=ignore_none, resolve_generics=resolve_generics))
        case _:
            bases.append(annotation)

    if ignore_none:
        bases = [b for b in bases if b is not type(None)]
        for i, b in enumerate(bases):
            if type(None) in (args := get_args(b)):
                bases[i] = Union[*(arg for arg in args if arg is not type(None))]

    if resolve_generics:
        for i, b in enumerate(bases):
            if not isinstance(b, TypeVar):
                continue

            if b.__constraints__:
                bases[i] = Union[*b.__constraints__]
            elif b.__bound__ is not None:
                bases[i] = b.__bound__

    return tuple(bases)


def get_bases[T](kls: type[BaseModel], expected: type[T]) -> Iterator[type[T]]:
    return (base for base in kls.__pydantic_parent_namespace__["bases"] if issubclass(base, expected))


def get_generics(kls: type[BaseModel]) -> tuple[type, ...]:
    """Get all generics from a model definition."""
    generics = kls.__pydantic_generic_metadata__["args"]
    generics = [
        Union[get_base_types(arg)] if len(get_base_types(arg)) > 1 else arg
        for arg in generics
    ]
    return tuple(arg for arg in generics if not is_typevar(arg))


def get_generic_type[T](
        generics: tuple[type, ...], expected: type[T], not_expected: type | None = None
) -> type[T] | Union[T]:
    for arg in generics:
        if isinstance(arg, type) and not_expected is not None and issubclass(arg, not_expected):
            continue

        if isinstance(arg, type) and issubclass(arg, expected):
            return arg
        if get_origin(arg) is UnionType and any(issubclass(arg, expected) for arg in get_base_types(arg)):
            return arg

    raise MyTunesTypeError(f"Could not find a {expected.__name__!r} generic type.")


def get_generic[T, B](
        kls: type[BaseModel], expected: type[T], not_expected: type | None = None, base: type[B] | None = None
) -> type[T] | Union[T]:
    """
    Get the exact generic type from a model definition.
    Provide an optional base type to look for in the model definition.
    """
    if base is None:
        generics = get_generics(kls)
    else:
        while not (generics := get_generics(kls)):
            kls = next(get_bases(kls, base))

    return get_generic_type(generics, expected, not_expected)
