from typing import ClassVar

from pydantic import Field

from musify.models.properties.uri import URI
from musify.models.api._endpoints import Endpoints, ReadItemEndpoints, ReadItemsEndpoints, \
    ReadSavedEndpoints, WriteSavedEndpoints, HasEndpoints
from musify.models.item.track import RemoteTrack


class TrackEndpoints[UT: URI, RT: RemoteTrack](Endpoints[UT, RT]):
    type: ClassVar[Type] = RemoteTrack


class TrackReadItemEndpoints[UT: URI, RT: RemoteTrack](
    TrackEndpoints[UT, RT], ReadItemEndpoints[UT, RT]
):
    pass


class TrackReadItemsEndpoints[UT: URI, RT: RemoteTrack](
    TrackEndpoints[UT, RT], ReadItemsEndpoints[UT, RT]
):
    pass


class TrackReadSavedEndpoints[UT: URI, RT: RemoteTrack](
    TrackEndpoints[UT, RT], ReadSavedEndpoints[UT, RT]
):
    pass


class TrackWriteSavedEndpoints[UT: URI, RT: RemoteTrack](
    TrackEndpoints[UT, RT], WriteSavedEndpoints[UT, RT]
):
    pass


class HasTrackEndpoints[ET: TrackEndpoints](HasEndpoints):
    tracks: ET = Field(
        description="Access track endpoints for the API."
    )
