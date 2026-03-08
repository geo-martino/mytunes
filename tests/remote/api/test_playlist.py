from musify.remote.collection.playlist import RemotePlaylist
from tests.remote.api.utils import MockRemoteResource


class MockRemotePlaylist(RemotePlaylist, MockRemoteResource):
    pass
