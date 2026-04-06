"""
Abstract base classes for all library models objects.
"""
from ._base import BaseModel, RootModel, ModelMetaclass
from ._base.attribute import AttributeModel
from ._base.enum import IntEnumModel
from ._base.resource import ResourceModel
from ._metaclass import makecls
