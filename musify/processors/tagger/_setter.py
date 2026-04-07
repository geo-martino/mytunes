from pydantic import BaseModel

from ..._models import ResourceModel


class TagSetter[IT: ResourceModel](BaseModel):
    """Sets tags on items according to some rules."""
