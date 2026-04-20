from collections.abc import Collection
from typing import Literal, ClassVar, Union, final

from yarl import URL

from ...._base.resource import ResourceModel
from mytunes.core.album import Album
from mytunes.core.track import Track
from mytunes.processors.download.stores._base import AudioStore
from mytunes.processors.download.stores.exception import StoreTypeError


@final
class JunoDownloadStore(AudioStore[Literal["juno"]]):
    __final__ = True

    _accepted_types: ClassVar[tuple[type[ResourceModel], ...]] = (Track, Album)

    @property
    def _base_url(self) -> URL:
        return URL.build(scheme="https", host=f"www.junodownload.com")

    def _format_query_path_for_item(self, item: Union[_accepted_types], query: str) -> str:
        return f"search/"

    def _format_query_params_for_item(
            self, item: Union[_accepted_types], query: str, fields: Collection[str]
    ) -> dict[str, str]:
        match item:
            case Track():
                item_type = "tracks"
            case Album():
                item_type = "releases"
            case _:
                raise StoreTypeError(f"Unrecognised item type: {type(item).__name__!r}")

        return {"q[all][0]": query, "list_view": item_type}
