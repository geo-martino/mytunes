from collections.abc import MutableMapping, Sequence
from typing import Any, Self

from pydantic import model_validator, validate_call

from mytunes._models.api import CollectionReadEndpoints
from mytunes._models.api.items import HasArtistEndpoints
from mytunes._models.collection._base import RemoteCollection, CollectionModel
from mytunes._models.collection.album import AlbumCollection
from mytunes._models.cursors import PageCursor
from mytunes._models.exception import MyTunesValidationError
from mytunes._models.item.album import HasAlbums, Album, RemoteAlbum
from mytunes._models.item.artist import Artist, RemoteArtist
from mytunes._models.item.genre import Genre, RemoteGenre
from mytunes._models.item.track import Track
from mytunes._models.properties.uri import URI


class ArtistCollection[AT: Album, GT: Genre](CollectionModel[AT], Artist[GT], HasAlbums[AT]):
    """Represents a collection of artists and their properties."""

    @property
    def _items(self) -> list[AT]:
        return self.albums

    @property
    def tracks(self) -> list[Track]:
        """The tracks on the albums by this artist."""
        return [track for album in self.albums if isinstance(album, AlbumCollection) for track in album.tracks]

    @model_validator(mode="before")
    @classmethod
    def _get_name_from_albums[T](cls, data: T | MutableMapping[str, Any]) -> T | MutableMapping[str, Any]:
        if not isinstance(data, MutableMapping):
            return data
        if isinstance(name := data.get(key := "name"), str) and name.strip():
            return data

        if not isinstance(albums := data.get("albums", []), Sequence):
            return data
        if not all(isinstance(album, Album) for album in albums):
            return data

        names = {album.artist for album in albums}
        if len(names) == 0:
            raise MyTunesValidationError("No artist given and no artists found in albums")
        if len(names) > 1:
            raise MyTunesValidationError(
                f"No artist given and albums are from different artists: {", ".join(map(str, names))}"
            )

        data[key] = names.pop()
        return data

    @model_validator(mode="before")
    @classmethod
    def _filter_albums_on_artist_name[T](cls, data: T | MutableMapping[str, Any]) -> T | MutableMapping[str, Any]:
        if not isinstance(data, MutableMapping):
            return data
        if not isinstance(albums := data.get(key := "albums"), Sequence):
            return data
        if not isinstance(name := data.get("name"), str) or not name.strip():
            return data

        data[key] = [album for album in albums if any(artist.name == name for artist in album.artists)]
        return data

    @model_validator(mode="after")
    def _check_albums_are_from_same_artist(self) -> Self:
        if not self.albums:
            return self

        for album in self.albums:
            names = {artist.name for artist in album.artists}
            if self.name not in names:
                raise MyTunesValidationError(
                    f"Album does not contain the artist {self.name!r}: {", ".join(map(str, names))}"
                )

        return self


class RemoteArtistCollection[UT: URI, AT: RemoteAlbum, GT: RemoteGenre, CT: PageCursor](
    ArtistCollection[AT, GT],
    RemoteArtist[UT, GT],
    RemoteCollection[UT, AT, CT],
):
    def _clear(self) -> None:
        self.albums.clear()

    @validate_call
    async def extend(self, api: HasArtistEndpoints[CollectionReadEndpoints]) -> None:
        self.albums[:] = await api.artists.get_all(self)
