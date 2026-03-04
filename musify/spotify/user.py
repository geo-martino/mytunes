from typing import final, ClassVar

from pydantic import Field
from musify.remote.user import RemoteUser
from musify.spotify._base import SpotifyResource
from musify.spotify.properties.images import HasSpotifyImages
from musify.spotify.properties.followers import HasFollowers
from musify.spotify.properties.uri import SpotifyUserURI


@final
class SpotifyUser(RemoteUser[SpotifyUserURI], SpotifyResource[SpotifyUserURI], HasSpotifyImages, HasFollowers):
    __final__ = True

    name: str = Field(
        description="The display name of the user",
        validation_alias="display_name",
    )
