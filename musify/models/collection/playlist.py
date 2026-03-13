from __future__ import annotations

from collections.abc import Iterable, Mapping
from copy import deepcopy
from typing import ClassVar, Annotated, TYPE_CHECKING, Self

from pydantic import Field, validate_call, BeforeValidator

from musify._types import StrippedString
from musify.models.collection._base import CollectionModel, RemoteCollection
from musify.models.cursors import PageCursor
from musify.models.item.track import Track, HasTracks, HasMutableTracks, RemoteTrack
from musify.models.mapping import UniqueMapping, MutableUniqueMapping
from musify.models.properties.image import HasImages
from musify.models.properties.length import HasLength
from musify.models.properties.name import HasName
from musify.models.properties.uri import HasURI, URI
from musify.models.remote import RemoteResource
from musify.models.user import RemoteUser

if TYPE_CHECKING:
    from musify.models.api.playlist import HasPlaylistEndpoints, PlaylistReadItemEndpoints, PlaylistReadWriteEndpoints


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

        See :py:meth:`.MutableUniqueSequence.merge` for more information.
        """
        self.tracks.merge(other.tracks, reference=reference.tracks if reference else None)


type MergePlaylistsType[K, V] = V | Iterable[V] | Mapping[K, V]


def _get_playlists_map_from_merge_input[TK, TV](
        playlists: MergePlaylistsType[TK, TV] | None
) -> MutableUniqueMapping[TK, TV] | None:
    match playlists:
        case None:
            return
        case MutableUniqueMapping():
            return playlists
        case HasMutablePlaylists():
            return playlists.playlists
        case HasPlaylists():
            return MutableUniqueMapping(playlists.playlists)
        case _:
            return MutableUniqueMapping(playlists)


type MergePlaylistsTypeAnnotated[TK, TV] = Annotated[
    MutableUniqueMapping[TK, TV] | None, BeforeValidator(_get_playlists_map_from_merge_input)
]


class HasPlaylists[TK, TV: Playlist](CollectionModel[TV]):
    """A mixin class to add a `playlists` field to a model."""
    playlists: UniqueMapping[TK, TV] = Field(
        description="The playlists in this collection",
        default_factory=UniqueMapping[TK, TV],
        frozen=True,
    )

    @property
    def _items(self) -> tuple[TV, ...]:
        return tuple(self.playlists.values())


class HasMutablePlaylists[TK, TV: MutablePlaylist](HasPlaylists[TK, TV]):
    """A mixin class to add a mutable `playlists` field to a model."""
    playlists: MutableUniqueMapping[TK, TV] = Field(
        description="The playlists in this collection",
        default_factory=MutableUniqueMapping[TK, TV],
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


class RemotePlaylist[TT: RemoteTrack, UT: URI, OT: RemoteUser, CT: PageCursor](
    Playlist[UT, TT, UT], RemoteResource[UT], RemoteCollection[TT, CT]
):
    owner: OT = Field(
        description="The owner of this playlist.",
    )
    public: bool | None = Field(
        description="Whether this playlist is publicly available.",
        default=None,
    )

    async def reload(self, api: HasPlaylistEndpoints[PlaylistReadItemEndpoints]) -> Self:
        return await api.playlists.get(self.uri)

    async def extend(self, api: HasPlaylistEndpoints[PlaylistReadWriteEndpoints]) -> None:
        await api.playlists.get_all(self.uri)


class RemoteMutablePlaylist[TT: RemoteTrack, UT: URI, OT: RemoteUser, CT: PageCursor](
    MutablePlaylist[UT, TT, UT], RemotePlaylist[TT, UT, OT, CT]
):
    pass
