from random import choice
from typing import ClassVar

from musify.remote import RemoteResource
from musify.remote.collection import RemoteCollection
from musify.remote.item.album import RemoteAlbum
from musify.remote.item.artist import RemoteArtist
from musify.remote.item.track import RemoteTrack
from tests.utils import SimpleURI


class MockRemoteResource(RemoteResource[SimpleURI]):
    source: ClassVar[str] = "mock"
    type: ClassVar[str] = choice((
        RemoteTrack.type,
        RemoteAlbum.type,
        RemoteArtist.type,
    ))


class MockRemoteCollection(MockRemoteResource, RemoteCollection):
    def _items(self) -> list:
        return []
