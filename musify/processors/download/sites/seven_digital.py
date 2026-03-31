from collections.abc import Collection, Sequence
from typing import Literal, ClassVar, Union, final

from pydantic import Field
from yarl import URL

from musify.models import ResourceModel
from musify.models.item.album import Album
from musify.models.item.artist import Artist
from musify.models.item.track import Track
from musify.processors.download.sites._base import AudioStore, HasLocale
from musify.processors.download.sites.exception import StoreTypeError


@final
class SevenDigitalStore(AudioStore[Literal["7digital"]], HasLocale):
    __final__ = True

    _accepted_types: ClassVar[tuple[type[ResourceModel], ...]] = (Track, Artist, Album)

    audio_types: Sequence[Literal[2, 9, 12, 16, 17, 19, 20]] = Field(
        description="The audio type codes to search for.",
        default=(2, 9, 12, 16, 17, 19, 20),
    )

    @property
    def _base_url(self) -> URL:
        lc = self.locale.split(".")  # TODO: fix this
        return URL.build(scheme="https", host=f"{lc}.7digital.com")

    def _format_query_path_for_item(self, item: Union[_accepted_types], query: str) -> str:
        match item:
            case Track():
                item_type = "track"
            case Artist():
                item_type = "artist"
            case Album():
                item_type = "release"
            case _:
                raise StoreTypeError(f"Unrecognised item type: {type(item)}")

        return f"search/{item_type}"

    def _format_query_params_for_item(
            self, item: Union[_accepted_types], query: str, fields: Collection[str]
    ) -> dict[str, str]:
        audio_types = ",".join(map(str, self.audio_types))
        return {"q": query, "f": audio_types}
