from typing import ClassVar

from mytunes._models.collection.library import RemoteLibrary


class MockRemoteLibrary(RemoteLibrary):
    source: ClassVar[str] = "test"
