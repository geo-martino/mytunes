from ._setter import ValueSetter, GroupSetter, SortSetter, IncrementalSetter
from ._tagger import Tagger, TaggerResult

__all__ = [
    Tagger.__name__,
    TaggerResult.__name__,
    ValueSetter.__name__,
    GroupSetter.__name__,
    SortSetter.__name__,
    IncrementalSetter.__name__,
]

# must import all the supported formats here so that they are registered in the registry
from .values import *
