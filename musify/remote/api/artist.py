from typing import ClassVar, Type

from pydantic import Field

from musify.models.properties.uri import URI
from musify.remote.api._endpoints import Endpoints, ReadItemEndpoints, ReadItemsEndpoints, \
    ReadSavedEndpoints, ReadCollectionEndpoints, WriteSavedEndpoints, HasEndpoints
from musify.remote.collection.artist import RemoteArtistCollection
from musify.remote.item.album import RemoteAlbum
from musify.remote.item.artist import RemoteArtist


class ArtistEndpoints[UT: URI, RT: RemoteArtist](Endpoints[UT, RT]):
    type: ClassVar[Type] = RemoteArtist


class ArtistReadItemEndpoints[UT: URI, RT: RemoteArtist](
    ArtistEndpoints[UT, RT], ReadItemEndpoints[UT, RT]
):
    pass


class ArtistReadItemsEndpoints[UT: URI, RT: RemoteArtist](
    ArtistEndpoints[UT, RT], ReadItemsEndpoints[UT, RT]
):
    pass


class ArtistReadCollectionEndpoints[UT: URI, RT: RemoteArtistCollection](
    ArtistEndpoints[UT, RT], ReadCollectionEndpoints[UT, RT]
):
    type: ClassVar[Type] = RemoteArtistCollection
    _extend_type: ClassVar[Type] = RemoteAlbum


class ArtistReadSavedEndpoints[UT: URI, RT: RemoteArtist](
    ArtistEndpoints[UT, RT], ReadSavedEndpoints[UT, RT]
):
    pass


class ArtistWriteSavedEndpoints[UT: URI, RT: RemoteArtist](
    ArtistEndpoints[UT, RT], WriteSavedEndpoints[UT, RT]
):
    pass


class HasArtistEndpoints[ET: ArtistEndpoints](HasEndpoints):
    artists: ET = Field(
        description="Access artist endpoints for the API."
    )
