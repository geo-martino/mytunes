from pydantic import field_validator

from musify.models.properties.image import HasImages
from musify.remote import RemoteModel


class HasSpotifyImages(HasImages):
    @field_validator("images", mode="before", check_fields=True)
    @classmethod
    def _validate_images[T](cls, images: T | list[dict]) -> T | dict[str, Any]:
        if not isinstance(images, list):
            return images

        images.sort(key=lambda i: i["height"], reverse=True)
        return {"main": images[0]} if images else {}
