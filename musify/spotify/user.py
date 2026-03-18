from typing import final, Annotated

from pydantic import Field

from musify._types import StrippedString
from musify.models._metadata import Attribute
from musify.models.user import RemoteUser
from musify.spotify._base import SpotifyResource
from musify.spotify.properties.images import HasSpotifyImages
from musify.spotify.properties.stats import HasFollowers
from musify.spotify.properties.uri import SpotifyUserURI


@final
class SpotifyUser(RemoteUser[SpotifyUserURI], SpotifyResource[SpotifyUserURI], HasSpotifyImages, HasFollowers):
    __final__ = True

    name: Annotated[StrippedString | None, Attribute()] = Field(
        description="The display name of the user",
        validation_alias="display_name",
    )
