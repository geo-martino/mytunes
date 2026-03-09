from typing import ClassVar

from pydantic import Field

from musify.models.properties.uri import URI
from musify.remote.api._endpoints import RemoteEndpoints, HasEndpoints
from musify.remote.collection.playlist import RemotePlaylist


class LibraryEndpoints[UT: URI, RT: RemotePlaylist](RemoteEndpoints[UT, RT]):
    type: ClassVar[str] = "library"


class HasLibraryEndpoints[ET: LibraryEndpoints](HasEndpoints):
    library: ET = Field(
        description="Access library endpoints for the API."
    )
