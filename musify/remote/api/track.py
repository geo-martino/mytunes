from typing import ClassVar

from pydantic import Field

from musify.models.properties.uri import URI
from musify.remote.api._endpoints import RemoteEndpoints, RemoteGetSingleEndpoints, RemoteGetManyEndpoints, \
    RemoteGetSavedEndpoints, RemoteMutableSavedEndpoints, HasEndpoints
from musify.remote.item.track import RemoteTrack


class TrackEndpoints[UT: URI, RT: RemoteTrack](RemoteEndpoints[UT, RT]):
    type: ClassVar[str] = "track"


class TrackGetSingleEndpoints[UT: URI, RT: RemoteTrack](
    TrackEndpoints[UT, RT], RemoteGetSingleEndpoints[UT, RT]
):
    pass


class TrackGetManyEndpoints[UT: URI, RT: RemoteTrack](
    TrackEndpoints[UT, RT], RemoteGetManyEndpoints[UT, RT]
):
    pass


class TrackGetSavedEndpoints[UT: URI, RT: RemoteTrack](
    TrackEndpoints[UT, RT], RemoteGetSavedEndpoints[UT, RT]
):
    pass


class TrackMutableSavedEndpoints[UT: URI, RT: RemoteTrack](
    TrackEndpoints[UT, RT], RemoteMutableSavedEndpoints[UT, RT]
):
    pass


class HasTrackEndpoints[ET: TrackEndpoints](HasEndpoints):
    tracks: ET = Field(
        description="Access track endpoints for the API."
    )
