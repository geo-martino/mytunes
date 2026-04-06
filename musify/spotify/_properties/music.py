from collections.abc import MutableMapping
from typing import Any

from pydantic import model_validator

from musify.models.properties.music import KeySignature, HasKeySignature


class HasSpotifyKeySignature(HasKeySignature):
    @model_validator(mode="before")
    @classmethod
    def _create_key_signature[T: MutableMapping[str, Any]](cls, data: T) -> T:
        if not isinstance(data, MutableMapping) or "key" not in data or "mode" not in data:
            return data

        if data["key"] == -1:
            data["key"] = None
            data.pop("mode")
        else:
            data["key"] = KeySignature(
                root=data.pop("key"),
                mode=data.pop("mode"),
            )
        return data
