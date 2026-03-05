from __future__ import annotations

from collections.abc import Iterable, Mapping
from copy import deepcopy
from typing import ClassVar, Annotated

from pydantic import Field, validate_call, BeforeValidator

from musify._types import StrippedString
from musify.models._base import CollectionModel
from musify.models.item.track import Track, HasTracks, HasMutableTracks
from musify.models.mapping import MusifyMapping, MusifyMutableMapping
from musify.models.properties.image import HasImages
from musify.models.properties.length import HasLength
from musify.models.properties.name import HasName
from musify.models.properties.uri import HasURI, URI


class Playlist[TK, TV: Track, UT: URI](HasTracks[TK, TV], HasName, HasURI[UT], HasLength, HasImages):
    """Represents a playlist collection and its properties."""
    type: ClassVar[str] = "playlist"

    description: StrippedString | None = Field(
        description="The description of the playlist.",
        default=None,
    )


class MutablePlaylist[TK, TV: Track, UT: URI](HasMutableTracks[TK, TV], Playlist[TK, TV, UT]):
    def merge(self, other: HasTracks[TK, TV], reference: HasTracks[TK, TV] | None = None) -> None:
        """
        Merge two playlists together.

        See :py:meth:`.MusifyMutableSequence.merge` for more information.
        """
        self.tracks.merge(other.tracks, reference=reference.tracks if reference else None)


type MergePlaylistsType[K, V] = V | Iterable[V] | Mapping[K, V]


def _get_playlists_map_from_merge_input[TK, TV](
        playlists: MergePlaylistsType[TK, TV] | None
) -> MusifyMutableMapping[TK, TV] | None:
    match playlists:
        case None:
            return
        case MusifyMutableMapping():
            return playlists
        case HasMutablePlaylists():
            return playlists.playlists
        case HasPlaylists():
            return MusifyMutableMapping(playlists.playlists)
        case _:
            return MusifyMutableMapping(playlists)


type MergePlaylistsTypeAnnotated[TK, TV] = Annotated[
    MusifyMutableMapping[TK, TV] | None, BeforeValidator(_get_playlists_map_from_merge_input)
]


class HasPlaylists[TK, TV: Playlist](CollectionModel):
    """A mixin class to add a `playlists` property to a MusifyCollection."""
    playlists: MusifyMapping[TK, TV] = Field(
        description="The playlists in this collection",
        default_factory=MusifyMapping[TK, TV],
        frozen=True,
    )


class HasMutablePlaylists[TK, TV: MutablePlaylist](HasPlaylists[TK, TV]):
    playlists: MusifyMutableMapping[TK, TV] = Field(
        description="The playlists in this collection",
        default_factory=MusifyMutableMapping[TK, TV],
        frozen=True,
    )

    @validate_call
    def merge_playlists(
            self, other: MergePlaylistsTypeAnnotated[TK, TV], reference: MergePlaylistsTypeAnnotated[TK, TV] = None
    ) -> None:
        """
        Merge playlists from given list/map/library to this library.

        If a matching playlist is found in the current models, :py:meth:`.Playlist.merge` is called on the
        current playlist with the other playlist.
        If a reference is provided and a match is found, this will be passed to :py:meth:`.Playlist.merge` too.
        If a playlist is not found in the current models, it will be added to the models.

        :param other: The playlists to merge into the current playlists.
        :param reference: The reference playlists to refer to when merging.
        """
        for name, playlist in other.items():
            if playlist not in self.playlists:
                self.playlists.add(deepcopy(playlist))
                continue

            self.playlists[playlist].merge(playlist, reference=reference[playlist] if reference else None)
