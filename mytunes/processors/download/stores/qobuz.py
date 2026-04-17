from collections.abc import Collection
from typing import Literal, Union, ClassVar, final

from yarl import URL

from ...._models import ResourceModel
from ...._models.item.album import Album
from ...._models.item.artist import Artist
from ...._models.item.track import Track
from mytunes.processors.download.stores._base import AudioStore, HasLocale


@final
class QobuzStore(AudioStore[Literal["qobuz"]], HasLocale):
    __final__ = True

    _accepted_types: ClassVar[tuple[type[ResourceModel], ...]] = (Track, Artist, Album)

    @property
    def _base_url(self) -> URL:
        return URL.build(scheme="https", host="www.qobuz.com")

    def _format_query_path_for_item(self, item: Union[_accepted_types], query: str) -> str:
        item_type = f"{item.type.rstrip("s")}s"
        lc_parts = self.locale.split(".")[0].split("_")
        lc = "-".join(reversed(lc_parts)).lower()
        return f"{lc}/search/{item_type}/{query}"

    def _format_query_params_for_item(
            self, item: Union[_accepted_types], query: str, fields: Collection[str]
    ) -> dict[str, str]:
        return {}
