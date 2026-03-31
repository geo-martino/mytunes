from collections.abc import Collection
from typing import Literal, ClassVar, Union, final

from yarl import URL

from musify.models import ResourceModel
from musify.models.item.album import Album
from musify.models.item.artist import Artist
from musify.models.item.track import Track
from musify.processors.download.sites._base import AudioStore, HasLocale
from musify.processors.download.sites.exception import StoreTypeError


@final
class JunoDownloadStore(AudioStore[Literal["juno"]]):
    __final__ = True

    _accepted_types: ClassVar[tuple[type[ResourceModel], ...]] = (Track, Album)

    @property
    def _base_url(self) -> URL:
        return URL.build(scheme="https", host=f"junodownload.com")

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
                raise StoreTypeError(f"Unrecognised item type: {type(item)}")

        return {"q[all][0]": query, "list_view": item_type}
