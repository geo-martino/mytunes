from ._manager import StoreManager

__all__ = [StoreManager.__name__]

# must import all the supported formats here so that they are registered in the registry
from .stores import *
