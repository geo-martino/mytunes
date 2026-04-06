from pydantic import BaseModel

from ..._models import ResourceModel


class TagSetter[IT: ResourceModel](BaseModel):
    """Sets tags on items according to some rules."""


class TagValue(BaseModel):
    """Gets tag values according to some rules."""


class TagTemplate(BaseModel):
    """Formats a tag value according to a template of tag values to get."""


class TagCondition(BaseModel):
    """Determines whether a tag should be set on an items according to the state of other tags of the item."""
