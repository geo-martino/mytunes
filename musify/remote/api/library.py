from aiorequestful.auth import Authoriser

from musify.models.properties.uri import URI
from musify.remote import RemoteModel
from musify.remote.api._base import RemoteEndpoints
from musify.remote.collection.playlist import RemotePlaylist


class LibraryEndpoints[AT: Authoriser, UT: URI, RT: RemotePlaylist](RemoteEndpoints[AT, UT, RT]):
    pass


class HasLibraryEndpoints[ET: LibraryEndpoints](RemoteModel):
    library: ET
