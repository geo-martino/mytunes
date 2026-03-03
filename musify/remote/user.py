from typing import ClassVar

from musify.models.properties.uri import URI
from musify.remote._base import RemoteResource


class RemoteUser[UT: URI](RemoteResource[UT]):
    type: ClassVar[str] = "user"
