from typing import ClassVar, Type

from pydantic import Field

from musify.models.api._endpoints import Endpoints, ItemReadEndpoints, BatchReadEndpoints, \
    BatchReadAllEndpoints, CollectionReadEndpoints, BatchWriteEndpoints, HasEndpoints, HasLibraryEndpoints
from musify.models.collection.artist import RemoteArtistCollection
from musify.models.item.album import RemoteAlbum
from musify.models.item.artist import RemoteArtist
from musify.models.properties.uri import URI


class ArtistEndpoints[UT: URI, RT: RemoteArtist](Endpoints[UT, RT]):
    type: ClassVar[Type] = RemoteArtist


class ArtistReadEndpoints[UT: URI, RT: RemoteArtist](
    ArtistEndpoints[UT, RT], ItemReadEndpoints[UT, RT]
):
    pass


class ArtistCollectionReadEndpoints[UT: URI, RT: RemoteArtistCollection, IT: RemoteAlbum](
    ArtistEndpoints[UT, RT], CollectionReadEndpoints[UT, RT, IT]
):
    type: ClassVar[Type] = RemoteArtistCollection
    _extend_type: ClassVar[Type] = RemoteAlbum


class ArtistBatchReadEndpoints[UT: URI, RT: RemoteArtist](
    ArtistEndpoints[UT, RT], BatchReadEndpoints[UT, RT]
):
    pass


class ArtistBatchReadAllEndpoints[UT: URI, RT: RemoteArtist](
    ArtistEndpoints[UT, RT], BatchReadAllEndpoints[UT, RT]
):
    pass


class ArtistBatchWriteEndpoints[UT: URI, RT: RemoteArtist](
    ArtistEndpoints[UT, RT], BatchWriteEndpoints[UT, RT]
):
    pass


class HasArtistEndpoints[ET: ArtistEndpoints | HasLibraryEndpoints](HasEndpoints):
    artists: ET = Field(
        description="Access artist endpoints for the API."
    )
