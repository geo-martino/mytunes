from typing import ClassVar

from pydantic import Field

from musify.models import AttributeModel
from musify.models.properties.uri import URI, HasURI


class RemoteModel(AttributeModel):
    source: ClassVar[str] = Field(
        description="The name of the source of this remote object.",
    )


class RemoteResource[UT: URI](RemoteModel, HasURI[UT]):
    uri: UT

    def __hash__(self):
        return hash(self.uri)
