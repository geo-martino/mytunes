import re
from typing import Self, ClassVar, Any, final

from pydantic import field_validator, model_validator
from pydantic_core.core_schema import ValidatorFunctionWrapHandler
from yarl import URL

from musify.exception import MusifyValueError
from musify.models.properties.uri import URI


class _SpotifyURIBase(URI):
    _source = "spotify"
    _version: ClassVar[str] = "v1"

    @property
    def source(self) -> str:
        return self.root.split(":")[0]

    @property
    def type(self) -> str:
        return self.root.split(":")[1]

    @property
    def id(self) -> str:
        return self.root.split(":")[2]

    @field_validator("root", mode="after")
    @classmethod
    def _validate_uri_length(cls, uri: str) -> str:
        if len(uri.split(":")) != 3:
            raise MusifyValueError("Invalid Spotify URI format. Expected format: {spotify}:{type}:{id}")
        return uri

    @classmethod
    def from_id(cls, value: Any, kind: str) -> Self:
        uri = ":".join((cls._source, kind, str(value)))
        return cls(uri)

    @property
    def api_url(self) -> URL:
        path = "/" + "/".join((self._version, self.type + "s", self.id))
        return URL.build(scheme="https", host="api.spotify.com", path=path)

    @classmethod
    def from_api_url[T](cls, value: T, handler: ValidatorFunctionWrapHandler) -> T | Self:
        if not isinstance(value, str | URL):
            return handler(value)

        if isinstance(value, str):
            if not re.match(r"^https?://api.spotify.com", value):
                return handler(value)
            value = URL(value)

        if value.host != "api.spotify.com":
            return handler(value)

        path_parts = value.path.strip("/").split("/")
        if len(path_parts) < 3:
            return handler(value)

        version, kind, id_value, *_ = path_parts
        return handler(":".join((cls._source, kind.rstrip("s"), str(id_value))))

    @property
    def public_url(self) -> URL:
        path = "/" + "/".join((self.type, self.id))
        return URL.build(scheme="https", host="open.spotify.com", path=path)

    @classmethod
    def from_public_url[T](cls, value: T | str | URL, handler: ValidatorFunctionWrapHandler) -> T | Self:
        if not isinstance(value, str | URL):
            return handler(value)

        if isinstance(value, str):
            if not re.match(r"^https?://open.spotify.com", value):
                return handler(value)
            value = URL(value)

        if value.host != "open.spotify.com":
            return handler(value)

        path_parts = value.path.strip("/").split("/")
        if len(path_parts) < 2:
            return handler(value)

        kind, id_value, *_ = path_parts
        return handler(":".join((cls._source, kind, str(id_value))))


@final
class SpotifyResourceURI(_SpotifyURIBase):
    __final__ = True

    @field_validator("root", mode="after")
    @classmethod
    def _validate_id_length(cls, uri: str) -> str:
        id_value = uri.split(":")[-1]
        if len(id_value) != 22:
            raise MusifyValueError("Invalid Spotify URI format. ID must be exactly 22 characters long.")
        return uri

    @model_validator(mode="after")
    def _type_is_not_user(self) -> Self:
        if self.type == "user":
            raise MusifyValueError("Spotify user URIs are not allowed for this model.")
        return self


@final
class SpotifyUserURI(_SpotifyURIBase):
    __final__ = True

    @model_validator(mode="after")
    def _type_is_user(self) -> Self:
        if self.type != "user":
            raise MusifyValueError("Only Spotify user URIs are allowed for this model.")
        return self
