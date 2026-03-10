from random import choice
from typing import ClassVar
from unittest.mock import patch, Mock

from aiorequestful.auth import Authoriser

from musify.remote import RemoteResource
from musify.remote.api import RemoteAPI, Endpoints, RemoteAuthoriser
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


class MockRemoteAuthoriser(RemoteAuthoriser[Mock]):
    client_id: str = "test_client_id"

    @patch.multiple(
        Authoriser,
        __abstractmethods__=set(),
        authorise=Mock(),
    )
    def create_authoriser(self) -> Authoriser:
        # noinspection PyAbstractClass
        return Authoriser()


class MockRemoteAPI(RemoteAPI[MockRemoteAuthoriser]):
    tracks: Endpoints
    artists: Endpoints
    albums: Endpoints
