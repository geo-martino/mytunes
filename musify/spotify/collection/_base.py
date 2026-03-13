from typing import final, Self

from pydantic import Field, AliasPath, model_validator

from musify._types import String
from musify.models.collection import PageCursor, RemoteCollection
from musify.spotify import SpotifyModel, SpotifyResource


@final
class SpotifyPageCursor(PageCursor, SpotifyModel):
    __final__ = True

    after: String | None = Field(
        description="The ID of the last item in the current page of items.",
        default=None,
        validation_alias=AliasPath("cursors", "after"),
    )


# noinspection PyAbstractClass
class SpotifyCollection[IT: SpotifyResource](SpotifyModel, RemoteCollection[IT, SpotifyPageCursor]):
    pass
