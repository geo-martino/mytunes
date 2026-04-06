from typing import Self, Any, final, ClassVar

from pydantic import field_validator, model_validator
from yarl import URL

from musify.models.exception import MusifyValidationError
from musify.models.properties.uri import URI
from musify.spotify._url import API_URL, PUBLIC_URL


class SpotifyURIBase(URI):
    _source: ClassVar[str] = "spotify"

    @property
    def _parts(self) -> tuple[str, str, str]:
        return self.root.split(":")

    @property
    def source(self) -> str:
        return self._parts[0]

    @property
    def type(self) -> str:
        return self._parts[1]

    @property
    def id(self) -> str:
        return self._parts[2]

    @model_validator(mode="after")
    def _validate_uri_length(self) -> Self:
        if len(self._parts) != 3:
            raise MusifyValidationError("Invalid Spotify URI format. Expected format: spotify:{type}:{id}")
        return self

    @classmethod
    def from_id(cls, value: Any, kind: str) -> Self:
        uri = ":".join((cls._source, kind, str(value)))
        return cls(uri)

    @property
    def api_url(self) -> URL:
        path = "/".join((self.type + "s", self.id))
        return API_URL.joinpath(path)

    @classmethod
    def from_api_url[T](cls, value: T) -> T | str:
        if not isinstance(value, str | URL):
            return value

        if isinstance(value, str):
            if not value.startswith(str(API_URL)):
                return value
            value = URL(value)

        if value.host != API_URL.host:
            return value

        path_parts = value.path.strip("/").split("/")
        if len(path_parts) < 3:
            return value

        version, kind, id_value, *_ = path_parts
        return ":".join((cls._source, kind.rstrip("s"), str(id_value)))

    @property
    def public_url(self) -> URL:
        path = "/" + "/".join((self.type, self.id))
        return URL.build(scheme=API_URL.scheme, host="open.spotify.com", path=path)

    @classmethod
    def from_public_url[T](cls, value: T) -> T | str:
        if not isinstance(value, str | URL):
            return value

        if isinstance(value, str):
            if not value.startswith(str(PUBLIC_URL)):
                return value
            value = URL(value)

        if value.host != PUBLIC_URL.host:
            return value

        path_parts = value.path.strip("/").split("/")
        if len(path_parts) < 2:
            return value

        kind, id_value, *_ = path_parts
        return ":".join((cls._source, kind, str(id_value)))


@final
class SpotifyResourceURI(SpotifyURIBase):
    __final__ = True

    @field_validator("root", mode="after")
    @classmethod
    def _validate_id_length(cls, uri: str) -> str:
        id_value = uri.split(":")[-1]
        if len(id_value) != 22 and id_value != cls._unavailable_id:
            raise MusifyValidationError("Invalid Spotify URI format. ID must be exactly 22 characters long.")
        return uri

    @model_validator(mode="after")
    def _type_is_not_user(self) -> Self:
        if self.type == "user":
            raise MusifyValidationError("Spotify user URIs are not allowed for this model.")
        return self


@final
class SpotifyUserURI(SpotifyURIBase):
    __final__ = True

    @model_validator(mode="after")
    def _type_is_user(self) -> Self:
        if self.type != "user":
            raise MusifyValidationError("Only Spotify user URIs are allowed for this model.")
        return self
