from random import choice
from typing import ClassVar
from unittest.mock import patch, Mock

from aiorequestful.auth import Authoriser

from musify.models.api.album import HasAlbumEndpoints
from musify.models.api.artist import HasArtistEndpoints
from musify.models.api.playlist import HasPlaylistEndpoints
from musify.models.api.track import HasTrackEndpoints
from musify.models.api.user import HasUserEndpoints
from musify.models.remote import RemoteResource
from musify.models.api import RemoteAPI, Endpoints, RemoteAuthoriser
from musify.models.collection import RemoteCollection
from musify.models.item.album import RemoteAlbum
from musify.models.item.artist import RemoteArtist
from musify.models.item.track import RemoteTrack
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


class MockRemoteAPI(
    RemoteAPI[MockRemoteAuthoriser],
    HasUserEndpoints[Endpoints],
    HasTrackEndpoints[Endpoints],
    HasArtistEndpoints[Endpoints],
    HasAlbumEndpoints[Endpoints],
    HasPlaylistEndpoints[Endpoints],
):
    pass
