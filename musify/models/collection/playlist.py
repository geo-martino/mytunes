from __future__ import annotations

from abc import abstractmethod
from collections.abc import Iterable, Mapping
from copy import deepcopy
from typing import ClassVar, Annotated, TYPE_CHECKING, Self, Union, Any

from pydantic import Field, validate_call, BeforeValidator, TypeAdapter, model_validator, computed_field, PositiveInt

from musify._types import StrippedString
from musify.exception import MusifyValueError
from musify.models._metaclass import makecls
from musify.models._metadata import Attribute
from musify.models.collection._base import CollectionModel, RemoteCollection, SyncResult
from musify.models.collection._sync import SYNC_TYPE, get_sync_items
from musify.models.cursors import PageCursor, InitialCursor
from musify.models.item.track import Track, HasTracks, HasMutableTracks, RemoteTrack
from musify.models.mapping import UniqueMapping, MutableUniqueMapping
from musify.models.properties.image import HasImages
from musify.models.properties.length import HasLength
from musify.models.properties.name import HasName
from musify.models.properties.uri import HasURI, URI
from musify.models.user import RemoteUser

if TYPE_CHECKING:
    from musify.models.api.playlist import HasPlaylistEndpoints, PlaylistReadItemEndpoints, PlaylistReadWriteEndpoints


class Playlist[TK, TV: Track, UT: URI](
    HasTracks[TK, TV], HasName, HasLength, HasImages, HasURI[UT], metaclass=makecls()
):
    """Represents a playlist collection and its properties."""
    type: ClassVar[str] = "playlist"

    description: Annotated[StrippedString | None, Attribute()] = Field(
        description="The description of the playlist.",
        default=None,
    )


class MutablePlaylist[TK, TV: Track, UT: URI](HasMutableTracks[TK, TV], Playlist[TK, TV, UT]):
    def merge(self, other: HasTracks[TK, TV] | Playlist, reference: HasTracks[TK, TV] | None = None) -> None:
        """
        Merge two playlists together by merging tracks and properties.

        See :py:meth:`.MutableUniqueSequence.merge` for more information.
        """
        self.tracks.merge(other.tracks, reference=reference.tracks if reference else None)
        if not isinstance(other, Playlist):
            return

        self.description = other.description
        self.images |= other.images


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
    playlists: Annotated[UniqueMapping[TK, TV], Attribute()] = Field(
        description="The playlists in this collection",
        default_factory=UniqueMapping[TK, TV],
        frozen=True,
    )

    @property
    def _items(self) -> tuple[TV, ...]:
        return tuple(self.playlists.values())


class HasMutablePlaylists[TK, TV: MutablePlaylist](HasPlaylists[TK, TV]):
    """A mixin class to add a mutable `playlists` field to a model."""
    playlists: Annotated[MutableUniqueMapping[TK, TV], Attribute()] = Field(
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


# noinspection PyAbstractClass
class RemotePlaylist[TT: RemoteTrack, UT: URI, OT: RemoteUser, CT: PageCursor](
    Playlist[UT, TT, UT], RemoteCollection[TT, UT, CT], metaclass=makecls()
):
    owner: Annotated[OT, Attribute()] = Field(
        description="The owner of this playlist.",
    )
    public: Annotated[bool | None, Attribute()] = Field(
        description="Whether this playlist is publicly available.",
        default=None,
    )

    @computed_field(description="The total number of items in this playlist")
    @property
    def item_total(self) -> PositiveInt | None:
        return self.cursor.total

    # @validate_call  # can't validate as can't import these types at runtime due to cyclical imports
    async def reload(self, api: HasPlaylistEndpoints[PlaylistReadItemEndpoints]) -> Self:
        return await api.playlists.get(self.uri)

    # @validate_call  # can't validate as can't import these types at runtime due to cyclical imports
    async def extend(self, api: HasPlaylistEndpoints[PlaylistReadWriteEndpoints]) -> None:
        # noinspection PyProtectedMember
        self.tracks._replace(await api.playlists.get_all(self))


class RemoteMutablePlaylist[TT: RemoteTrack, UT: URI, OT: RemoteUser, CT: PageCursor](
    MutablePlaylist[UT, TT, UT], RemotePlaylist[TT, UT, OT, CT]
):
    async def sync_items(
            self,
            api: HasPlaylistEndpoints[PlaylistReadWriteEndpoints],
            kind: SYNC_TYPE = "new",
            dry_run: bool = False,
            show_bar: bool = True,
    ) -> SyncResult:
        """
        Synchronise the current playlist's items with the remote service.

        Sync options:
            * 'new': Do not clear any items from the remote playlist and only add new items.
            * 'refresh': Clear all items from the remote playlist first, then add all items from this playlist object.
            * 'sync': Clear all items not currently on the remote playlist first, then add all items
                from this playlist not currently in the remote playlist.

        :param api: The API to use for synchronisation.
        :param kind: Sync option for the remote playlist. See description.
        :param dry_run: Run function, but do not modify the remote playlists at all.
        :param show_bar: Show progress bars during sync.
        :return: The results of the sync as a :py:class:`SyncResult` object.
        """
        initial = [track.uri for track in self.tracks if track.uri]
        remote = await self._get_remote_uris(api, show_bar=show_bar)
        add, remove, unchanged = get_sync_items(kind, initial=initial, remote=remote)

        removed = await api.playlists.remove(
            self.uri.api_url, uris=remove, show_bar=show_bar
        ) if not dry_run else len(remove)
        added = await api.playlists.add(
            self.uri.api_url, uris=add, show_bar=show_bar
        ) if not dry_run else len(add)

        return SyncResult(
            start=len(remote),
            added=added,
            removed=removed,
            unchanged=len(unchanged),
            difference=added - removed,
            final=len(remote) + added - removed
        )

    async def _get_remote_uris(
            self, api: HasPlaylistEndpoints[PlaylistReadWriteEndpoints], show_bar: bool = True
    ) -> list[UT]:
        # noinspection PyTypeChecker
        cursor_classes = [kls for kls in InitialCursor.registered_submodels if kls.source == self.source]
        cursor = TypeAdapter(Union[*cursor_classes]).validate_python(self.uri.api_url)
        return [track.uri for track in await api.playlists.get_all(cursor, show_bar=show_bar)]
