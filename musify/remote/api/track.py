from aiorequestful.auth import Authoriser

from musify.models.properties.uri import URI
from musify.remote import RemoteModel
from musify.remote.api._base import RemoteEndpoints
from musify.remote.item.track import RemoteTrack


class TrackEndpoints[AT: Authoriser, UT: URI, RT: RemoteTrack](RemoteEndpoints[AT, UT, RT]):
    pass


class TrackSavedEndpoints[AT: Authoriser, UT: URI, RT: RemoteTrack](RemoteEndpoints[AT, UT, RT]):
    pass


class HasTrackEndpoints[ET: TrackEndpoints](RemoteModel):
    tracks: ET
