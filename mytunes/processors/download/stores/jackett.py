from collections.abc import Collection, Sequence
from typing import Literal, ClassVar, Union, final

from pydantic import Field
from yarl import URL

from ...._models import ResourceModel
from ...._models.item.album import Album
from ...._models.item.artist import Artist
from ...._models.item.track import Track
from mytunes._types import HttpURL
from mytunes.processors.download.stores._base import AudioStore


@final
class JackettStore(AudioStore[Literal["jackett"]]):
    __final__ = True

    _accepted_types: ClassVar[tuple[type[ResourceModel], ...]] = (Track, Artist, Album)

    url: HttpURL = Field(
        description="The base URL of the app.",
    )
    categories: Sequence[int] = Field(
        description="The category codes to search for.",
        default=(3000, 3010, 3020, 3030, 3040, 3050, 3060),
    )

    @property
    def _base_url(self) -> URL:
        return self.url.with_path("UI/Dashboard")

    def _format_query_path_for_item(self, item: Union[_accepted_types], query: str) -> str:
        return ""

    def _format_query_params_for_item(
            self, item: Union[_accepted_types], query: str, fields: Collection[str]
    ) -> dict[str, str]:
        categories = ",".join(map(str, self.categories))
        return {"search": query, "categories": categories}
