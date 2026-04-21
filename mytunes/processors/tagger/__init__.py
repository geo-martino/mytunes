from ._setter import ValueSetter, GroupedSetter, SortedSetter, IncrementalSetter
from ._tagger import Tagger

__all__ = [
    Tagger.__name__,
    ValueSetter.__name__,
    GroupedSetter.__name__,
    SortedSetter.__name__,
    IncrementalSetter.__name__,
]

# must import all the supported formats here so that they are registered in the registry
from .values import *
