from abc import abstractmethod
from typing import ClassVar, TYPE_CHECKING, Self

from pydantic import Field

from musify.models import BaseModel
from musify.models.properties.uri import URI, HasURI

if TYPE_CHECKING:
    from musify.models.api import HasEndpoints


class RemoteModel(BaseModel):
    source: ClassVar[str] = Field(
        description="The name of the source of this remote object.",
    )


# noinspection PyAbstractClass
class RemoteResource[UT: URI](RemoteModel, HasURI[UT]):
    uri: UT

    def __hash__(self):
        return hash(self.uri)

    @abstractmethod
    def reload(self, api: HasEndpoints) -> Self:
        """
        Reload this remote resource using the provided API.
        Returns a new instance of the resource with the updated data.
        Does not modify the existing instance.
        """
        raise NotImplementedError
