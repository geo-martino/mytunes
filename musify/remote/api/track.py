from aiorequestful.auth import Authoriser

from musify.models.properties.uri import URI
from musify.remote import RemoteModel
from musify.remote.api._base import RemoteEndpoints, RemoteGetSingleEndpoints, RemoteGetManyEndpoints, \
    RemoteSavedEndpoints
from musify.remote.item.track import RemoteTrack


class TrackEndpoints[AT: Authoriser, UT: URI, RT: RemoteTrack](RemoteEndpoints[AT, UT, RT]):
    pass


class TrackGetSingleEndpoints[AT: Authoriser, UT: URI, RT: RemoteTrack](
    TrackEndpoints[AT, UT, RT], RemoteGetSingleEndpoints[AT, UT, RT]
):
    pass


class TrackGetManyEndpoints[AT: Authoriser, UT: URI, RT: RemoteTrack](
    TrackEndpoints[AT, UT, RT], RemoteGetManyEndpoints[AT, UT, RT]
):
    pass


class TrackSavedEndpoints[AT: Authoriser, UT: URI, RT: RemoteTrack](
    TrackEndpoints[AT, UT, RT], RemoteSavedEndpoints[AT, UT, RT]
):
    pass


class HasTrackEndpoints[ET: TrackEndpoints](RemoteModel):
    tracks: ET
