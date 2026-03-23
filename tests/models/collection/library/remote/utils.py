from typing import ClassVar

from musify.models.collection.library import RemoteLibrary


class MockRemoteLibrary(RemoteLibrary):
    source: ClassVar[str] = "test"
