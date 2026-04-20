from typing import ClassVar

from mytunes.core._collection.library import RemoteLibrary


class MockRemoteLibrary(RemoteLibrary):
    source: ClassVar[str] = "Test"
