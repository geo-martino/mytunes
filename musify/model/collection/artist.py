from collections.abc import MutableMapping, Sequence
from typing import Any, Self

from pydantic import model_validator

from musify.exception import MusifyValueError
from musify.model.item.album import HasAlbums, Album
from musify.model.item.artist import Artist
from musify.model.item.genre import Genre
from musify.model.item.track import HasTracks, Track


class ArtistCollection[TK, TV: Track, AT: Album, GT: Genre](Artist[GT], HasTracks[TK, TV], HasAlbums[AT]):
    """Represents a collection of artists and their properties."""
    # noinspection PyNestedDecorators
    @model_validator(mode="before")
    @staticmethod
    def _get_name_from_albums(data: MutableMapping[str, Any]) -> Any:
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
            raise MusifyValueError("No artist given and no artists found in albums")
        if len(names) > 1:
            raise MusifyValueError(
                f"No artist given and albums are from different artists: {", ".join(map(str, names))}"
            )

        data[key] = names.pop()
        return data

    # noinspection PyNestedDecorators
    @model_validator(mode="before")
    @staticmethod
    def _filter_albums_on_artist_name(data: MutableMapping[str, Any]) -> Any:
        if not isinstance(data, MutableMapping):
            return data
        if not isinstance(albums := data.get(key := "albums"), Sequence):
            return data
        if not isinstance(name := data.get("name"), str) or not name.strip():
            return data

        data[key] = [album for album in albums if any(artist.name == name for artist in album.artists)]
        return data

    # noinspection PyNestedDecorators
    @model_validator(mode="after")
    def _check_albums_are_from_same_artist(self) -> Self:
        if not self.albums:
            return self

        names = {album.artist for album in self.albums}
        if len(names) > 1:
            raise MusifyValueError(f"Albums are from different artists: {", ".join(map(str, names))}")

        return self.albums
