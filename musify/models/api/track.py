from typing import ClassVar, Type

from pydantic import Field

from musify.models.api._endpoints import Endpoints, ItemReadEndpoints, BatchReadEndpoints, \
    BatchReadAllEndpoints, BatchWriteEndpoints, HasEndpoints, HasLibraryEndpoints
from musify.models.item.track import RemoteTrack
from musify.models.properties.uri import URI


class TrackEndpoints[UT: URI, RT: RemoteTrack](Endpoints[UT, RT]):
    type: ClassVar[Type] = RemoteTrack


class TrackReadEndpoints[UT: URI, RT: RemoteTrack](
    TrackEndpoints[UT, RT], ItemReadEndpoints[UT, RT]
):
    pass


class TrackBatchReadEndpoints[UT: URI, RT: RemoteTrack](
    TrackEndpoints[UT, RT], BatchReadEndpoints[UT, RT]
):
    pass


class TrackBatchReadAllEndpoints[UT: URI, RT: RemoteTrack](
    TrackEndpoints[UT, RT], BatchReadAllEndpoints[UT, RT]
):
    pass


class TrackBatchWriteEndpoints[UT: URI, RT: RemoteTrack](
    TrackEndpoints[UT, RT], BatchWriteEndpoints[UT, RT]
):
    pass


class HasTrackEndpoints[ET: TrackEndpoints | HasLibraryEndpoints](HasEndpoints):
    tracks: ET = Field(
        description="Access track endpoints for the API."
    )
