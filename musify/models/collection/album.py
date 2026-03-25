from collections.abc import Sequence, MutableMapping
from typing import Self, Any, TYPE_CHECKING

from pydantic import model_validator, ModelWrapValidatorHandler, computed_field, PositiveInt

from musify.models.collection._base import RemoteCollection
from musify.models.cursors import PageCursor
from musify.models.exception import MusifyValidationError
from musify.models.item.album import Album, RemoteAlbum
from musify.models.item.artist import Artist, RemoteArtist
from musify.models.item.genre import Genre, RemoteGenre
from musify.models.item.track import Track, HasTracks, RemoteTrack
from musify.models.properties.uri import URI

if TYPE_CHECKING:
    from musify.models.api.album import HasAlbumEndpoints, AlbumReadCollectionEndpoints


class AlbumCollection[TK, TV: Track, RT: Artist, GT: Genre](HasTracks[TK, TV], Album[RT, GT]):
    # noinspection PyNestedDecorators
    @model_validator(mode="wrap")
    @classmethod
    def _get_name_from_tracks(cls, data: MutableMapping[str, Any], handler: ModelWrapValidatorHandler[Self]) -> Self:
        if not isinstance(data, MutableMapping):
            return handler(data)
        if isinstance(name := data.get(key := "name"), str) and name.strip():
            return handler(data)

        if not isinstance(tracks := data.get("tracks", []), Sequence):
            return handler(data)
        if not all(isinstance(track, Track) for track in tracks):
            return handler(data)

        names = {track.album.name if track.album is not None else None for track in tracks}
        if len(names) == 0:
            raise MusifyValidationError("No album name given and no album names found in tracks")
        if len(names) > 1:
            raise MusifyValidationError(
                f"No album name given and tracks are from different albums: {", ".join(map(str, names))}"
            )

        data[key] = names.pop()
        return handler(data)

    # noinspection PyNestedDecorators
    @model_validator(mode="wrap")
    @classmethod
    def _filter_tracks_on_album_name(
            cls, data: MutableMapping[str, Any], handler: ModelWrapValidatorHandler[Self]
    ) -> Self:
        if not isinstance(data, MutableMapping):
            return handler(data)
        if not isinstance(tracks := data.get(key := "tracks"), Sequence):
            return handler(data)
        if not isinstance(name := data.get("name"), str) or not name.strip():
            return handler(data)

        data[key] = [track for track in tracks if track.album is not None and track.album.name == name]
        return handler(data)

    # noinspection PyNestedDecorators
    @model_validator(mode="after")
    def _check_tracks_are_from_same_album(self) -> Self:
        if not self.tracks:
            return self

        names = {track.album.name if track.album is not None else None for track in self.tracks}
        if len(set(filter(lambda x: x is not None, names))) > 1:
            raise MusifyValidationError(f"Tracks are from different albums: {", ".join(map(str, names))}")

        return self


class RemoteAlbumCollection[UT: URI, TT: RemoteTrack, RT: RemoteArtist, GT: RemoteGenre, CT: PageCursor](
    AlbumCollection[UT, TT, RT, GT],
    RemoteAlbum[URI, RT, GT],
    RemoteCollection[UT, TT, CT],
):
    @computed_field(description="The total number of tracks in this album")
    @property
    def track_total(self) -> PositiveInt | None:
        return self.cursor.total

    # @validate_call  # can't validate as can't import these types at runtime due to cyclical imports
    async def extend(self, api: HasAlbumEndpoints[AlbumReadCollectionEndpoints]) -> None:
        # noinspection PyProtectedMember
        self.tracks._replace(await api.albums.get_all(self))
