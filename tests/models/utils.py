from random import choice
from typing import ClassVar, Self

from musify.models.api import HasEndpoints
from musify.models.collection import RemoteCollection
from musify.models.item.album import RemoteAlbum
from musify.models.item.artist import RemoteArtist
from musify.models.item.track import RemoteTrack
from musify.models.remote import RemoteResource
from tests.utils import SimpleURI


class MockRemoteResource(RemoteResource[SimpleURI]):
    source: ClassVar[str] = "mock"
    type: ClassVar[str] = choice((
        RemoteTrack.type,
        RemoteAlbum.type,
        RemoteArtist.type,
    ))

    async def reload(self, api: HasEndpoints) -> Self:
        return self


class MockRemoteCollection(MockRemoteResource, RemoteCollection):
    type: ClassVar[str] = MockRemoteResource.type

    @property
    def _items(self) -> list:
        return []

    async def extend(self, api: HasEndpoints) -> None:
        pass
