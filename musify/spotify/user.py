from typing import Any

from pydantic import Field, PositiveInt, AliasPath, field_validator, Json

from musify.remote.user import RemoteUser
from musify.spotify.properties.uri import SpotifyUserURI


class SpotifyUser(RemoteUser[SpotifyUserURI]):
    name: str = Field(
        description="The display name of the user",
        validation_alias="display_name",
    )
    followers: PositiveInt = Field(
        description="The number of followers of the user",
        validation_alias=AliasPath("followers", "total"),
    )
    uri: SpotifyUserURI  # TODO: This shouldn't be needed...

    @field_validator("images", mode="before", check_fields=True)
    @classmethod
    def _validate_images[T](cls, images: T | list[dict]) -> T | dict[str, Any]:
        if not isinstance(images, list):
            return images

        images.sort(key=lambda i: i["height"], reverse=True)
        return {"main": images[0]} if images else {}
