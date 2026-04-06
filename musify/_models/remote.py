from abc import abstractmethod
from typing import ClassVar, TYPE_CHECKING, Annotated

from pydantic import Field

from musify._models import BaseModel
from musify._models._metaclass import makecls
from musify._models.metadata import UniqueAttribute
from musify._models.properties.uri import URI, HasImmutableURI

if TYPE_CHECKING:
    from musify._models.api import HasEndpoints


class RemoteModel(BaseModel):
    source: ClassVar[str] = Field(
        description="The name of the source of this remote object.",
    )


# noinspection PyAbstractClass
class RemoteResource[UT: URI](HasImmutableURI[UT], RemoteModel, metaclass=makecls()):
    uri: Annotated[UT, UniqueAttribute()]

    def __hash__(self):
        return hash(self.uri)

    @abstractmethod
    async def reload(self, api: HasEndpoints) -> None:
        """Reload this remote resource using the provided API."""
        raise NotImplementedError
