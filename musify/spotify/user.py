from pydantic import Field

from musify.remote.user import RemoteUser
from musify.spotify._base import SpotifyResource
from musify.spotify.properties.images import HasSpotifyImages
from musify.spotify.properties.followers import HasFollowers
from musify.spotify.properties.uri import SpotifyUserURI


class SpotifyUser(SpotifyResource[SpotifyUserURI], RemoteUser[SpotifyUserURI], HasSpotifyImages, HasFollowers):
    name: str = Field(
        description="The display name of the user",
        validation_alias="display_name",
    )
    uri: SpotifyUserURI  # TODO: This shouldn't be needed...
