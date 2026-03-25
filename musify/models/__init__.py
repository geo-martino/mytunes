"""
Abstract base classes for all library models objects.
"""
from ._attribute import AttributeModel
from ._base import BaseModel, RootModel
from ._enum import IntEnumModel
from ._metaclass import makecls
from ._property import abstract_property
from ._resource import ResourceModel
