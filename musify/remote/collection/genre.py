from musify.models.collection.genre import GenreCollection
from musify.models.properties.uri import URI
from musify.remote._base import RemoteResource
from musify.remote.collection._base import RemoteCollection
from musify.remote.item.genre import RemoteGenre
from musify.remote.item.track import RemoteTrack


class RemoteGenreCollection[UT: URI, TK, TV: RemoteTrack](
    RemoteResource[UT], RemoteCollection, RemoteGenre[UT], GenreCollection[TK, TV]
):
    pass
