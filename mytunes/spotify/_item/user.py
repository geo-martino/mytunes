from typing import final, Annotated

from mytunes._types import StrippedString
from mytunes.core.user import RemoteUser
from mytunes.spotify._base import SpotifyResource
from pydantic import Field

from .._properties.images import HasSpotifyImages
from .._properties.stats import HasFollowers
from .._properties.uri import SpotifyUserURI
from ..._base.attribute import Attribute


@final
class SpotifyUser(RemoteUser[SpotifyUserURI], HasSpotifyImages, HasFollowers, SpotifyResource[SpotifyUserURI]):
    __final__ = True

    name: Annotated[StrippedString | None, Attribute()] = Field(
        description="The display name of the user",
        validation_alias="display_name",
    )
