from abc import abstractmethod
from collections.abc import Mapping
from typing import Any, ClassVar, Self, Annotated, Union

from mytunes._models._base.attribute import AttributeMetaclass
from mytunes._models._base.resource import ResourceMetaclass
from mytunes._models.exception import MyTunesValidationError
from pydantic import Field, Tag, Discriminator

from mytunes._models import ResourceModel
from mytunes._models._metaclass import makecls
from mytunes._models.collection import CollectionModel
from mytunes._models.collection.playlist import Playlist, HasPlaylists, HasMutablePlaylists
from mytunes._models.item.track import Track, HasTracks, HasMutableTracks
from mytunes._models.properties.asynch import HasAsyncOperations
from mytunes._models.properties.logger import HasLogger, HasProgress
from mytunes.processors.filters.composite import IncludeExcludeFilter
from mytunes.processors.filters.values import NameFilter


class HasTracksAndPlaylists[TK, TV: Track, KP, VP: Playlist](
    CollectionModel[TV], HasTracks[TK, TV], HasPlaylists[KP, VP],
):
    @property
    def _items(self) -> list[TV]:
        return list(self.tracks)

    def dump(self) -> dict[str, Any]:
        """Generate a dump of this library's state. This can be used for backup or debugging purposes."""
        return self.model_dump(mode="json", exclude_none=True)


class LibraryMetaclass(AttributeMetaclass, ResourceMetaclass):
    @property
    def annotation(cls) -> Self:
        def _get_source_from_config[T](data: T | Mapping[str, Any]) -> str:
            match data:
                case Library():
                    return data.source
                case Mapping():
                    return data.get("source")
                case _:
                    raise MyTunesValidationError(f"Unrecognised type: {type(data).__name__!r}.")

        classes = cls.registered_submodels
        types = (Annotated[kls, Tag(kls.source)] for kls in classes)
        return Annotated[
            Union[*types],
            Field(discriminator=Discriminator(_get_source_from_config)),
        ]


# noinspection PyAbstractClass
class Library[TK, TV: Track, KP, VP: Playlist](
    ResourceModel,
    HasTracksAndPlaylists[TK, TV, KP, VP],
    HasAsyncOperations,
    HasLogger,
    HasProgress,
    metaclass=LibraryMetaclass
):
    """A library of tracks and playlists and other object types."""
    type: ClassVar[str] = "library"

    source: ClassVar[str] = Field(
        description="The name of the source of this library.",
    )

    playlist_filter: NameFilter | IncludeExcludeFilter[VP, NameFilter, NameFilter] | None = Field(
        description="The filter to apply when loading playlists. Filters playlist by name.",
        default=None,
        repr=False,
    )

    @abstractmethod
    async def load(self):
        """Loads all resources in this library and log results. Replaces all loaded resources."""
        raise NotImplementedError

    @abstractmethod
    async def load_tracks(self) -> Any:
        """Loads all tracks available for this library. Replaces all currently loaded tracks."""
        raise NotImplementedError

    @abstractmethod
    def log_tracks(self) -> None:
        """Log stats on currently loaded tracks"""
        raise NotImplementedError

    @abstractmethod
    async def load_playlists(self) -> Any:
        """
        Load all playlists available for this library filtered down using the ``playlist_filter`` if given.
        Replaces all currently loaded playlists.
        """
        raise NotImplementedError

    @abstractmethod
    def log_playlists(self) -> None:
        """Log stats on currently loaded playlists"""
        raise NotImplementedError


# noinspection PyAbstractClass
class MutableLibrary[TK, TV: Track, KP, VP: Playlist](
    HasMutableTracks[TK, TV], HasMutablePlaylists[KP, VP], Library[TK, TV, KP, VP]
):
    """A mutable library of tracks and playlists and other object types."""
