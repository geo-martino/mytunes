from pydantic import ConfigDict

from musify.models import BaseModel


class Result(BaseModel):
    """Stores the results of an operation"""
    model_config = ConfigDict(frozen=True)
