from typing import ClassVar, Type

from pydantic import Field

from musify.models.api._endpoints import Endpoints, ItemReadEndpoints, BatchReadEndpoints, \
    BatchReadAllEndpoints, BatchWriteEndpoints, CollectionReadEndpoints, HasEndpoints, HasLibraryEndpoints
from musify.models.collection.album import RemoteAlbumCollection
from musify.models.item.album import RemoteAlbum
from musify.models.item.track import RemoteTrack
from musify.models.properties.uri import URI


class AlbumEndpoints[UT: URI, RT: RemoteAlbum](Endpoints[UT, RT]):
    type: ClassVar[Type] = RemoteAlbum


class AlbumReadEndpoints[UT: URI, RT: RemoteAlbum](
    AlbumEndpoints[UT, RT], ItemReadEndpoints[UT, RT]
):
    pass


class AlbumBatchReadEndpoints[UT: URI, RT: RemoteAlbum](
    AlbumEndpoints[UT, RT], BatchReadEndpoints[UT, RT]
):
    pass


class AlbumCollectionReadEndpoints[UT: URI, RT: RemoteAlbumCollection, IT: RemoteTrack](
    AlbumEndpoints[UT, RT], CollectionReadEndpoints[UT, RT, IT]
):
    type: ClassVar[Type] = RemoteAlbumCollection
    _extend_type: ClassVar[Type] = RemoteTrack


class AlbumBatchReadAllEndpoints[UT: URI, RT: RemoteAlbum](
    AlbumEndpoints[UT, RT], BatchReadAllEndpoints[UT, RT]
):
    pass


class AlbumBatchWriteEndpoints[UT: URI, RT: RemoteAlbum](
    AlbumEndpoints[UT, RT], BatchWriteEndpoints[UT, RT]
):
    pass


class HasAlbumEndpoints[ET: AlbumEndpoints | HasLibraryEndpoints](HasEndpoints):
    albums: ET = Field(
        description="Access album endpoints for the API."
    )
