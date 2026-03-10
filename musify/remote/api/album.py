from typing import ClassVar, Type

from pydantic import Field

from musify.models.properties.uri import URI
from musify.remote.api._endpoints import RemoteEndpoints, RemoteGetSingleEndpoints, RemoteGetManyEndpoints, \
    RemoteGetSavedEndpoints, RemoteMutableSavedEndpoints, RemoteCollectionEndpoints, HasEndpoints
from musify.remote.collection.album import RemoteAlbumCollection
from musify.remote.item.album import RemoteAlbum
from musify.remote.item.track import RemoteTrack


class AlbumEndpoints[UT: URI, RT: RemoteAlbum](RemoteEndpoints[UT, RT]):
    type: ClassVar[Type] = RemoteAlbum


class AlbumGetSingleEndpoints[UT: URI, RT: RemoteAlbum](
    AlbumEndpoints[UT, RT], RemoteGetSingleEndpoints[UT, RT]
):
    pass


class AlbumGetManyEndpoints[UT: URI, RT: RemoteAlbum](
    AlbumEndpoints[UT, RT], RemoteGetManyEndpoints[UT, RT]
):
    pass


class AlbumCollectionEndpoints[UT: URI, RT: RemoteAlbumCollection](
    AlbumEndpoints[UT, RT], RemoteCollectionEndpoints[UT, RT]
):
    type: ClassVar[Type] = RemoteAlbumCollection
    _extend_type: ClassVar[Type] = RemoteTrack


class AlbumGetSavedEndpoints[UT: URI, RT: RemoteAlbum](
    AlbumEndpoints[UT, RT], RemoteGetSavedEndpoints[UT, RT]
):
    pass


class AlbumMutableSavedEndpoints[UT: URI, RT: RemoteAlbum](
    AlbumEndpoints[UT, RT], RemoteMutableSavedEndpoints[UT, RT]
):
    pass


class HasAlbumEndpoints[ET: AlbumEndpoints](HasEndpoints):
    albums: ET = Field(
        description="Access album endpoints for the API."
    )
