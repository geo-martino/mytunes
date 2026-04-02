from pydantic_core import PydanticUseDefault


def default_if_none[T](value: T) -> T:
    """Use the Pydantic default if value is None."""
    if value is None:
        raise PydanticUseDefault()
    return value
