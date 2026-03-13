from typing import final

from pydantic import Field, AliasPath

from musify._types import String
from musify.models.cursors import PageCursor, KeyCursor, IndexCursor, UrlCursor, InitialCursor
from musify.spotify import SpotifyModel


class SpotifyPageCursor(PageCursor, SpotifyModel):
    pass


@final
class SpotifyIndexCursor(SpotifyPageCursor, IndexCursor):
    __final__ = True


@final
class SpotifyKeyCursor(SpotifyPageCursor, KeyCursor):
    __final__ = True

    before: String | None = Field(
        description="The key to get the previous page of items",
        default=None,
        validation_alias=AliasPath("cursors", "before"),
    )
    after: String | None = Field(
        description="The key to get the next page of items",
        default=None,
        validation_alias=AliasPath("cursors", "after"),
    )


@final
class SpotifyUrlCursor(SpotifyPageCursor, UrlCursor):
    __final__ = True


@final
class SpotifyInitialCursor(SpotifyPageCursor, InitialCursor):
    __final__ = True
