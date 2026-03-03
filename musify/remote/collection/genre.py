from typing import final


from musify.models.collection.genre import GenreCollection
from musify.models.properties.uri import URI
from musify.remote.collection._base import RemoteCollection
from musify.remote.item.genre import RemoteGenre
from musify.remote.item.track import RemoteTrack


class RemoteGenreCollection[UT: URI, TK, TV: RemoteTrack](
    RemoteCollection[UT], RemoteGenre[UT], GenreCollection[TK, TV]
):
    pass
