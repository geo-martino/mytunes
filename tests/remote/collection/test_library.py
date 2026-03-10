import pytest

from musify.remote.api import RemoteAPI
from musify.remote.collection.library import RemoteLibrary, RemoteMutableLibrary
from tests.models.testers import MusifyModelTester
from tests.remote.api.utils import MockRemoteAPI


class TestRemoteLibrary(MusifyModelTester):

    @pytest.fixture
    def api(self) -> RemoteAPI:
        return MockRemoteAPI()

    @pytest.fixture
    def model(self, api: RemoteAPI) -> RemoteLibrary:
        return RemoteLibrary(api=api)


class TestRemoteMutableLibrary(MusifyModelTester):
    @pytest.fixture
    def api(self) -> RemoteAPI:
        return MockRemoteAPI()

    @pytest.fixture
    def model(self, api: RemoteAPI) -> RemoteMutableLibrary:
        return RemoteMutableLibrary(api=api)
