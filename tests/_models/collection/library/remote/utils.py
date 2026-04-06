from typing import ClassVar

from musify._models.collection.library import RemoteLibrary


class MockRemoteLibrary(RemoteLibrary):
    source: ClassVar[str] = "test"
