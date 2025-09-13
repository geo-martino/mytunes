"""
Property models allow for property-specific validation and manipulation.

For properties which are common across multiple models, we also define Attribute models to help identify models
which make use of these common properties. By convention, they are usually denoted by their prefix
like `Has...` or `Is...`.
"""
from ._core import HasSeparableTags
