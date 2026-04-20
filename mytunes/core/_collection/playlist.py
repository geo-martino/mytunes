from __future__ import annotations

from collections.abc import Iterable, Mapping
from copy import deepcopy
from typing import ClassVar, Annotated, TYPE_CHECKING, Self, overload, Any

from pydantic import Field, validate_call, BeforeValidator, computed_field, PositiveInt, model_validator
from pydantic.json_schema import JsonSchemaValue
from pydantic_core.core_schema import ValidationInfo

from mytunes._types import StrippedString
from mytunes.core._collection import SyncRemoteResult
from mytunes.core._collection._base import CollectionModel, RemoteCollection
from mytunes.core._collection._sync import SYNC_TYPE, get_sync_items
from mytunes.core._context import RemoteModelContext
from mytunes.core.api import HasLibraryEndpoints
from mytunes.core.cursors import PageCursor
from mytunes.core.sequence import UniqueSequence, MutableUniqueSequence
from mytunes.exception import MyTunesValidationError
from mytunes.processors.filters.compare import ComparerFilter
from mytunes.core.properties.image import HasImages
from mytunes.core.properties.length import HasLength
from mytunes.core.properties.name import HasName
from mytunes.core.properties.uri import URI
from .._item.track import Track, HasTracks, HasMutableTracks, RemoteTrack
from .._item.user import RemoteUser
from ..._base import makecls
from ..._base.attribute import AttributeModel, Attribute
from ..._base.resource import ResourceModel

if TYPE_CHECKING:
    from mytunes.core.api.playlist import HasPlaylistEndpoints, PlaylistReadEndpoints, \
        PlaylistReadWriteEndpoints, PlaylistLibraryEndpoints


class Playlist[TT: Track](
    CollectionModel[TT], HasTracks[TT], HasName, HasLength, HasImages, ResourceModel, metaclass=makecls()
):
    """Represents a playlist collection and its properties."""
    type: ClassVar[str] = "playlist"

    description: Annotated[StrippedString | None, Attribute()] = Field(
        description="The description of the playlist.",
        default=None,
    )

    @property
    def _items(self) -> UniqueSequence[TT]:
        return self.tracks


class MutablePlaylist[TT: Track](HasMutableTracks[TT], Playlist[TT]):
    def merge(self, other: HasTracks[TT] | Playlist, reference: HasTracks[TT] | None = None) -> None:
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


def _get_playlists_map_from_merge_input[PT](
        playlists: MergePlaylistsType[PT] | None
) -> MutableUniqueSequence[Any, PT] | None:
    match playlists:
        case None:
            return
        case MutableUniqueSequence():
            return playlists
        case HasMutablePlaylists():
            return playlists.playlists
        case HasPlaylists():
            return MutableUniqueSequence(playlists.playlists)
        case _:
            return MutableUniqueSequence(playlists)


type MergePlaylistsTypeAnnotated[PT] = Annotated[
    MutableUniqueSequence[Any, PT] | None,
    BeforeValidator(_get_playlists_map_from_merge_input)
]


class HasPlaylists[PT: Playlist](AttributeModel):
    """A mixin class to add a `playlists` field to a model."""
    playlists: Annotated[UniqueSequence[Any, PT], Attribute()] = Field(
        description="The playlists in this collection",
        default_factory=UniqueSequence[Any, PT],
        frozen=True,
        repr=False,
    )


class HasMutablePlaylists[PT: MutablePlaylist](HasPlaylists[PT]):
    """A mixin class to add a mutable `playlists` field to a model."""
    playlists: Annotated[MutableUniqueSequence[Any, PT], Attribute()] = Field(
        description="The playlists in this collection",
        default_factory=MutableUniqueSequence[Any, PT],
        frozen=True,
        repr=False,
    )

    @overload
    def merge_playlists(
            self, other: MergePlaylistsType[PT], reference: MergePlaylistsType[PT] = None
    ) -> None: ...

    @overload
    def merge_playlists(
            self, other: MergePlaylistsTypeAnnotated[PT], reference: MergePlaylistsTypeAnnotated[PT] = None
    ) -> None: ...

    @validate_call
    def merge_playlists(
            self, other: MergePlaylistsTypeAnnotated[PT], reference: MergePlaylistsTypeAnnotated[PT] = None
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
        for playlist in other:
            if playlist not in self.playlists:
                self.playlists.append(deepcopy(playlist))
                continue

            reference_playlist = reference.get(playlist) if reference else None
            self.playlists[playlist].merge(playlist, reference=reference_playlist)


# noinspection PyAbstractClass
class RemotePlaylist[UT: URI, TT: RemoteTrack, OT: RemoteUser, CT: PageCursor](
    Playlist[TT], RemoteCollection[UT, TT, CT], metaclass=makecls()
):
    owner: Annotated[OT, Attribute()] = Field(
        description="The owner of this playlist.",
    )
    public: Annotated[bool | None, Attribute()] = Field(
        description="Whether this playlist is publicly available.",
        default=None,
    )

    @computed_field(description="The total number of items in this playlist", repr=False)
    @property
    def item_total(self) -> PositiveInt | None:
        return self.cursor.total

    def _clear(self) -> None:
        # noinspection PyProtectedMember
        self.tracks._replace(())

    @staticmethod
    def _get_context_user(info: ValidationInfo) -> OT | None:
        if not (context := info.context) or not isinstance(context, RemoteModelContext) or context.user is None:
            return
        return context.user

    @model_validator(mode="after")
    def _validate_mutability(self, info: ValidationInfo) -> Self:
        if (user := self._get_context_user(info)) is None:
            return self

        if user == self.owner:
            raise MyTunesValidationError(
                f"Currently authenticated user is the owner of this playlist "
                f"({self.owner.name!r} == {user.name!r}), which implies that this playlist is mutable. "
                "Use the appropriate mutable playlist type to validate this playlist instead."
            )

        return self

    # @validate_call  # can't validate as can't import these types at runtime due to cyclical imports
    async def reload(self, api: HasPlaylistEndpoints[PlaylistReadEndpoints]) -> Self:
        model = await api.playlists.get(self.uri)
        self.__dict__.update(model.__dict__)
        return model

    # @validate_call  # can't validate as can't import these types at runtime due to cyclical imports
    async def extend(self, api: HasPlaylistEndpoints[PlaylistReadWriteEndpoints]) -> None:
        # noinspection PyProtectedMember
        self.tracks._replace(await api.playlists.get_all(self))


class RemoteMutablePlaylist[UT: URI, TT: RemoteTrack, OT: RemoteUser, CT: PageCursor](
    MutablePlaylist[TT], RemotePlaylist[UT, TT, OT, CT]
):
    @model_validator(mode="after")
    def _validate_mutability(self, info: ValidationInfo) -> Self:
        if (user := self._get_context_user(info)) is None:
            return self

        if user != self.owner:
            raise MyTunesValidationError(
                "Currently authenticated user is not the owner of this playlist "
                f"({self.owner.name!r} != {user.name!r}), which implies that this playlist is immutable. "
                "Use the appropriate immutable playlist type to validate this playlist instead."
            )

        return self

    # @validate_call  # can't validate as can't import these types at runtime due to cyclical imports
    async def sync_properties(
            self,
            api: HasPlaylistEndpoints[HasLibraryEndpoints[PlaylistLibraryEndpoints]],
            dry_run: bool = False,
    ) -> JsonSchemaValue:
        """
        Synchronise the current playlist's properties with the remote service.
        This may include the name, description and other properties depending on the remote service.

        :param api: The API to use for synchronisation.
        :param dry_run: Run function, but do not modify the remote playlists at all.
        :return: The properties synchronised.
        """
        body = self._get_properties_body()
        if not dry_run:
            await api.playlists.library.modify(self.uri.api_url, **body)

        return body

    def _get_properties_body(self) -> JsonSchemaValue:
        return dict(
            name=self.name,
            description=self.description,
            public=self.public,
        )

    # @validate_call  # can't validate as can't import these types at runtime due to cyclical imports
    async def sync_items(
            self,
            api: HasPlaylistEndpoints[PlaylistReadWriteEndpoints],
            kind: SYNC_TYPE = "new",
            items_filter: ComparerFilter | None = None,
            dry_run: bool = False,
    ) -> SyncRemoteResult:
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
        :param items_filter: An optional filter to apply to items before syncing.
            Only items that pass the filter will be synced.
        :return: The sync result.
        """
        tracks = items_filter.apply(self.tracks) if items_filter else self.tracks
        initial = [track.uri for track in tracks if track.uri]
        remote = await self._get_remote_uris(api)
        add, remove, unchanged = get_sync_items(kind, initial=initial, remote=remote)

        removed = await api.playlists.remove(self.uri, uris=remove) if not dry_run else len(remove)
        added = await api.playlists.add(self.uri, uris=add) if not dry_run else len(add)

        return SyncRemoteResult(
            start=len(remote),
            added=added,
            removed=removed,
            unchanged=len(unchanged),
            difference=added - removed,
            final=len(remote) + added - removed
        )

    async def _get_remote_uris(self, api: HasPlaylistEndpoints[PlaylistReadWriteEndpoints]) -> list[UT]:
        playlist = await api.playlists.get(self.uri.api_url)
        return [track.uri for track in await api.playlists.get_all(playlist)]
