from typing import Annotated

from annotated_types import MinLen
from pydantic import StringConstraints, BeforeValidator
from pydantic.alias_generators import to_snake

type Character = Annotated[str, StringConstraints(min_length=1, max_length=1)]
type StrippedCharacter = Annotated[str, StringConstraints(min_length=1, max_length=1, strip_whitespace=True)]
type String = Annotated[str, StringConstraints(min_length=1)]
type StrippedString = Annotated[str, StringConstraints(min_length=1, strip_whitespace=True)]
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
