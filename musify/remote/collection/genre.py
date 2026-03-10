from musify.models.collection.genre import GenreCollection
from musify.models.properties.uri import URI
from musify.models.sequence import MusifySequence
from musify.remote._base import RemoteResource
from musify.remote.collection._base import RemoteCollection, ItemsCursor
from musify.remote.item.genre import RemoteGenre
from musify.remote.item.track import RemoteTrack


class RemoteGenreCollection[UT: URI, TT: RemoteTrack, CT: ItemsCursor](
    GenreCollection[UT, TT],
    RemoteGenre[UT],
    RemoteResource[UT],
    RemoteCollection[TT, CT],
):
    pass
