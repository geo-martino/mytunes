from pydantic import Field

from .._base import BaseModel
from ._item.user import RemoteUser


class RemoteModelContext(BaseModel):
    """Additional context to be provided when creating models from API responses."""
    user: RemoteUser | None = Field(
        description="The currently authenticated user, if available.",
        default=None,
    )
    type: str | None = Field(
        description="The type of the resource, if available.",
        default=None,
    )
