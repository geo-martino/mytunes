import functools
from abc import abstractmethod
from typing import Callable, Any


def abstract_property(func: Callable[[Any], Any]) -> property:
    """
    Create a new abstract property for an attribute.

    This is just a convenience decorator for combining `property` and `abstractmethod` decorators i.e.

    ```python
        @property
        @abstractmethod
        def my_property(self):
            ...
    ```
    """
    @functools.wraps(func)
    def wrapper(self):
        return func(self)
    return property(abstractmethod(wrapper))
