from contextlib import suppress
from dataclasses import dataclass, field
from http import HTTPMethod
from typing import Any

from aiorequestful.cache.backend.base import ResponseRepositorySettings
from aiorequestful.types import MethodInput
from mytunes.core.properties.uri import URI
from mytunes.spotify import SpotifyModel
from pydantic import ValidationError
from yarl import URL


# TODO: drop this on aiorequestful v2
@dataclass
class SpotifyRepositorySettings(ResponseRepositorySettings):

    @property
    def fields(self) -> tuple[str, ...]:
        return "id",

    def get_key(self, method: MethodInput, url: URL, **__) -> tuple[str | None, ...]:
        if HTTPMethod(method) != HTTPMethod.GET:
            return (None,)

        with suppress(ValidationError):
            return URI.get_adapter_for_source(SpotifyModel.source).validate_python(url).id,
        return (None,)

    def get_name(self, payload: dict[str, Any]) -> str | None:
        if payload.get("type") == "user":
            return payload["display_name"]
        return payload.get("name")


# TODO: drop this on aiorequestful v2
@dataclass
class SpotifyIndexCursorRepositorySettings(SpotifyRepositorySettings):

    default_limit: int = field(default=20)

    @property
    def fields(self) -> tuple[str, ...]:
        return *super().fields, "offset", "size"

    def get_key(self, method: MethodInput, url: URL, **__) -> tuple[str | int | None, ...]:
        base = super().get_key(method=method, url=url)
        return *base, self.get_offset(url), self.get_limit(url)

    @staticmethod
    def get_offset(url: URL) -> int:
        """Extracts the offset for a paginated request from the given ``url``."""
        params = URL(url).query
        return int(params.get("offset", 0))

    def get_limit(self, url: URL) -> int:
        """Extracts the limit for a paginated request from the given ``url``."""
        params = URL(url).query
        return int(params.get("limit", self.default_limit))
