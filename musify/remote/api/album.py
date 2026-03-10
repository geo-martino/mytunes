from typing import ClassVar, Type

from pydantic import Field

from musify.models.properties.uri import URI
from musify.remote.api._endpoints import Endpoints, ReadItemEndpoints, ReadItemsEndpoints, \
    ReadSavedEndpoints, WriteSavedEndpoints, ReadCollectionEndpoints, HasEndpoints
from musify.remote.collection.album import RemoteAlbumCollection
from musify.remote.item.album import RemoteAlbum
from musify.remote.item.track import RemoteTrack


class AlbumEndpoints[UT: URI, RT: RemoteAlbum](Endpoints[UT, RT]):
    type: ClassVar[Type] = RemoteAlbum


class AlbumReadItemEndpoints[UT: URI, RT: RemoteAlbum](
    AlbumEndpoints[UT, RT], ReadItemEndpoints[UT, RT]
):
    pass


class AlbumReadItemsEndpoints[UT: URI, RT: RemoteAlbum](
    AlbumEndpoints[UT, RT], ReadItemsEndpoints[UT, RT]
):
    pass


class AlbumReadCollectionEndpoints[UT: URI, RT: RemoteAlbumCollection](
    AlbumEndpoints[UT, RT], ReadCollectionEndpoints[UT, RT]
):
    type: ClassVar[Type] = RemoteAlbumCollection
    _extend_type: ClassVar[Type] = RemoteTrack


class AlbumReadSavedEndpoints[UT: URI, RT: RemoteAlbum](
    AlbumEndpoints[UT, RT], ReadSavedEndpoints[UT, RT]
):
    pass


class AlbumWriteSavedEndpoints[UT: URI, RT: RemoteAlbum](
    AlbumEndpoints[UT, RT], WriteSavedEndpoints[UT, RT]
):
    pass


class HasAlbumEndpoints[ET: AlbumEndpoints](HasEndpoints):
    albums: ET = Field(
        description="Access album endpoints for the API."
    )
