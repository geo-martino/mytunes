from pydantic import Field

from musify.models import BaseModel
from musify.models.user import RemoteUser


class RemoteModelContext(BaseModel):
    """Additional context to be provided when creating models from API responses."""
    user: RemoteUser | None = Field(
        description="The currently authenticated user, if available.",
        default=None,
    )
