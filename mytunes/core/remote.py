from abc import abstractmethod
from typing import ClassVar, TYPE_CHECKING, Annotated, Self

from pydantic import Field

from mytunes.core.properties.uri import URI, HasImmutableURI
from .._base import BaseModel, make_cls
from .._base.resource import UniqueAttribute

if TYPE_CHECKING:
    from mytunes.core.api import HasEndpoints


class RemoteModel(BaseModel):
    source: ClassVar[str] = Field(
        description="The name of the source of this remote object.",
    )


# noinspection PyAbstractClass
class RemoteResource[UT: URI](HasImmutableURI[UT], RemoteModel, metaclass=make_cls()):
    # we just need to make this field required
    uri: Annotated[UT, UniqueAttribute()] = Field(
        description="The URI for this resource on the remote service.",
        frozen=True,
    )

    def __hash__(self):
        return hash(self.uri)

    @abstractmethod
    async def reload(self, api: HasEndpoints) -> Self:
        """
        Reload this remote resource using the provided API.
        Returns the response model from the API which will always be a different instance to this resource.
        """
        raise NotImplementedError
