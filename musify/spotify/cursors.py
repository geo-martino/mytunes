# TODO: move this on aiorequestful v2
from typing import final, Annotated

from pydantic import Field, AliasPath

from musify._models.cursors import PageCursor, KeyCursor, IndexCursor, UrlCursor, InitialCursor
from musify._models.metadata import Attribute
from musify._types import String
from musify.spotify import SpotifyModel


# noinspection PyAbstractClass
class SpotifyPageCursor(PageCursor, SpotifyModel):
    pass


@final
class SpotifyIndexCursor(SpotifyPageCursor, IndexCursor):
    __final__ = True


@final
class SpotifyKeyCursor(SpotifyPageCursor, KeyCursor):
    __final__ = True

    before: Annotated[String | None, Attribute()] = Field(
        description="The key to get the previous page of items",
        default=None,
        validation_alias=AliasPath("cursors", "before"),
    )
    after: Annotated[String | None, Attribute()] = Field(
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
