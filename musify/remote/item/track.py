from pydantic import Field

from musify.models.item.track import Track
from musify.models.properties.uri import URI
from musify.remote._base import RemoteResource
from musify.remote.item.album import RemoteAlbum
from musify.remote.item.artist import RemoteArtist
from musify.remote.item.genre import RemoteGenre


class RemoteTrack[RT: RemoteArtist, AT: RemoteAlbum, GT: RemoteGenre, UT: URI](
        Track[RT, AT, GT, UT],
        RemoteResource[UT],
):
    artists: list[RT] = Field(
        description="The artists associated with this resource.",
        default_factory=list,
    )
