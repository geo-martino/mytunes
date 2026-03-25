from collections.abc import MutableMapping, Sequence
from typing import Any, Self, TYPE_CHECKING

from pydantic import model_validator, ModelWrapValidatorHandler

from musify.models.collection._base import RemoteCollection
from musify.models.collection.album import AlbumCollection
from musify.models.cursors import PageCursor
from musify.models.exception import MusifyValidationError
from musify.models.item.album import HasAlbums, Album, RemoteAlbum
from musify.models.item.artist import Artist, RemoteArtist
from musify.models.item.genre import Genre, RemoteGenre
from musify.models.item.track import Track
from musify.models.properties.uri import URI

if TYPE_CHECKING:
    from musify.models.api.artist import HasArtistEndpoints, ArtistReadCollectionEndpoints


class ArtistCollection[AT: Album, GT: Genre](Artist[GT], HasAlbums[AT]):
    """Represents a collection of artists and their properties."""
    @property
    def _items(self) -> list[AT]:
        # mro doesn't always use get albums, overriding to ensure albums are returned
        return self.albums

    @property
    def tracks(self) -> list[Track]:
        """The tracks on the albums by this artist."""
        return [track for album in self.albums if isinstance(album, AlbumCollection) for track in album.tracks]

    # noinspection PyNestedDecorators
    @model_validator(mode="wrap")
    @classmethod
    def _get_name_from_albums(cls, data: MutableMapping[str, Any], handler: ModelWrapValidatorHandler[Self]) -> Self:
        if not isinstance(data, MutableMapping):
            return handler(data)
        if isinstance(name := data.get(key := "name"), str) and name.strip():
            return handler(data)

        if not isinstance(albums := data.get("albums", []), Sequence):
            return handler(data)
        if not all(isinstance(album, Album) for album in albums):
            return handler(data)

        names = {album.artist for album in albums}
        if len(names) == 0:
            raise MusifyValidationError("No artist given and no artists found in albums")
        if len(names) > 1:
            raise MusifyValidationError(
                f"No artist given and albums are from different artists: {", ".join(map(str, names))}"
            )

        data[key] = names.pop()
        return handler(data)

    # noinspection PyNestedDecorators
    @model_validator(mode="wrap")
    @classmethod
    def _filter_albums_on_artist_name(
            cls, data: MutableMapping[str, Any], handler: ModelWrapValidatorHandler[Self]
    ) -> Self:
        if not isinstance(data, MutableMapping):
            return handler(data)
        if not isinstance(albums := data.get(key := "albums"), Sequence):
            return handler(data)
        if not isinstance(name := data.get("name"), str) or not name.strip():
            return handler(data)

        data[key] = [album for album in albums if any(artist.name == name for artist in album.artists)]
        return handler(data)

    # noinspection PyNestedDecorators
    @model_validator(mode="after")
    def _check_albums_are_from_same_artist(self) -> Self:
        if not self.albums:
            return self

        for album in self.albums:
            names = {artist.name for artist in album.artists}
            if self.name not in names:
                raise MusifyValidationError(
                    f"Album does not contain the artist {self.name!r}: {", ".join(map(str, names))}"
                )

        return self


class RemoteArtistCollection[UT: URI, AT: RemoteAlbum, GT: RemoteGenre, CT: PageCursor](
    ArtistCollection[AT, GT],
    RemoteArtist[UT, GT],
    RemoteCollection[UT, AT, CT],
):
    # @validate_call  # can't validate as can't import these types at runtime due to cyclical imports
    async def extend(self, api: HasArtistEndpoints[ArtistReadCollectionEndpoints]) -> None:
        # noinspection PyProtectedMember
        self.albums[:] = await api.artists.get_all(self)
