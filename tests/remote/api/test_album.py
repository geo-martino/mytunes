from musify.remote.item.album import RemoteAlbum
from tests.remote.api.utils import MockRemoteResource


class MockRemoteAlbum(RemoteAlbum, MockRemoteResource):
    pass
