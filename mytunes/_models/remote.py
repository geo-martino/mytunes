from abc import abstractmethod
from typing import ClassVar, TYPE_CHECKING, Annotated

from pydantic import Field

from mytunes._models import BaseModel
from mytunes._models._metaclass import makecls
from mytunes._models.metadata import UniqueAttribute
from mytunes._models.properties.uri import URI, HasImmutableURI

if TYPE_CHECKING:
    from mytunes._models.api import HasEndpoints


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
