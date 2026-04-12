from collections.abc import Collection
from typing import Literal, ClassVar, Union, final

from yarl import URL

from ...._models import ResourceModel
from ...._models.item.album import Album
from ...._models.item.artist import Artist
from ...._models.item.track import Track
from mytunes.processors.download.stores._base import AudioStore
from mytunes.processors.download.stores.exception import StoreTypeError


@final
class BandcampStore(AudioStore[Literal["bandcamp"]]):
    __final__ = True

    _accepted_types: ClassVar[tuple[type[ResourceModel], ...]] = (Track, Artist, Album)

    @property
    def _base_url(self) -> URL:
        return URL.build(scheme="https", host="bandcamp.com")

    def _format_query_path_for_item(self, item: Union[_accepted_types], query: str) -> str:
        return "search"

    def _format_query_params_for_item(
            self, item: Union[_accepted_types], query: str, fields: Collection[str]
    ) -> dict[str, str]:
        match item:
            case Track():
                item_type = "t"
            case Artist():
                item_type = "b"
            case Album():
                item_type = "a"
            case _:
                raise StoreTypeError(f"Unrecognised item type: {type(item).__name__!r}")

        return {"q": query, "item_type": item_type}
