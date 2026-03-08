from musify.models.collection.genre import GenreCollection
from musify.models.item.track import HasMutableTracks
from musify.models.properties.uri import URI
from musify.models.sequence import MusifySequence
from musify.remote._base import RemoteResource
from musify.remote.collection._base import RemoteCollection
from musify.remote.item.genre import RemoteGenre
from musify.remote.item.track import RemoteTrack


class RemoteGenreCollection[UT: URI, TT: RemoteTrack](
    GenreCollection[UT, TT],
    RemoteGenre[UT],
    RemoteResource[UT],
    RemoteCollection,
):
    @property
    def _items(self) -> MusifySequence:
        return self.tracks
