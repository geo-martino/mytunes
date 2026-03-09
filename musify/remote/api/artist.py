from typing import ClassVar, Type

from aiorequestful.auth import Authoriser
from pydantic import Field

from musify.models.properties.uri import URI
from musify.remote import RemoteModel
from musify.remote.api._endpoints import RemoteEndpoints, RemoteGetSingleEndpoints, RemoteGetManyEndpoints, \
    RemoteGetSavedEndpoints, RemoteCollectionEndpoints, RemoteMutableSavedEndpoints, HasEndpoints
from musify.remote.collection.artist import RemoteArtistCollection
from musify.remote.item.artist import RemoteArtist


class ArtistEndpoints[UT: URI, RT: RemoteArtist](RemoteEndpoints[UT, RT]):
    type: ClassVar[Type] = RemoteArtist


class ArtistGetSingleEndpoints[UT: URI, RT: RemoteArtist](
    ArtistEndpoints[UT, RT], RemoteGetSingleEndpoints[UT, RT]
):
    pass


class ArtistGetManyEndpoints[UT: URI, RT: RemoteArtist](
    ArtistEndpoints[UT, RT], RemoteGetManyEndpoints[UT, RT]
):
    pass


class ArtistCollectionEndpoints[UT: URI, RT: RemoteArtistCollection](
    ArtistEndpoints[UT, RT], RemoteCollectionEndpoints[UT, RT]
):
    type: ClassVar[Type] = RemoteArtistCollection
    _extend_type: ClassVar[str] = "album"


class ArtistGetSavedEndpoints[UT: URI, RT: RemoteArtist](
    ArtistEndpoints[UT, RT], RemoteGetSavedEndpoints[UT, RT]
):
    pass


class ArtistMutableSavedEndpoints[UT: URI, RT: RemoteArtist](
    ArtistEndpoints[UT, RT], RemoteMutableSavedEndpoints[UT, RT]
):
    pass


class HasArtistEndpoints[ET: ArtistEndpoints](HasEndpoints):
    artists: ET = Field(
        description="Access artist endpoints for the API."
    )
