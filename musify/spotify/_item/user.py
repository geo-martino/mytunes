from typing import final, Annotated

from pydantic import Field

from musify._models.item.user import RemoteUser
from musify._models.metadata import Attribute
from musify._types import StrippedString
from musify.spotify._base import SpotifyResource
from .._properties.images import HasSpotifyImages
from .._properties.stats import HasFollowers
from .._properties.uri import SpotifyUserURI


@final
class SpotifyUser(RemoteUser[SpotifyUserURI], SpotifyResource[SpotifyUserURI], HasSpotifyImages, HasFollowers):
    __final__ = True

    name: Annotated[StrippedString | None, Attribute()] = Field(
        description="The display name of the user",
        validation_alias="display_name",
    )
