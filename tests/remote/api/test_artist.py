from musify.remote.item.artist import RemoteArtist
from tests.remote.api.utils import MockRemoteResource


class MockRemoteArtist(RemoteArtist, MockRemoteResource):
    pass
