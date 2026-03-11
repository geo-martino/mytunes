from typing import ClassVar

from pydantic import Field

from musify.models.properties.uri import URI
from musify.models.api._endpoints import Endpoints, HasEndpoints
from musify.models.collection.playlist import RemotePlaylist


class LibraryEndpoints[UT: URI, RT: RemotePlaylist](Endpoints[UT, RT]):
    type: ClassVar[Type] = RemotePlaylist


class HasLibraryEndpoints[ET: LibraryEndpoints](HasEndpoints):
    library: ET = Field(
        description="Access library endpoints for the API."
    )
