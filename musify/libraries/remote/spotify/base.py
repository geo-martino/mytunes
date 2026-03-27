"""
Core abstract classes for the :py:mod:`Spotify` module.

These define the foundations of any Spotify object or item.
"""
from abc import ABCMeta

from yarl import URL

from musify.libraries.remote.core.base import RemoteObject, RemoteItem
from musify.libraries.remote.core.exception import RemoteObjectTypeError, RemoteError
from musify.libraries.remote.core.types import RemoteObjectType
from musify.libraries.remote.spotify.api import SpotifyAPI


class SpotifyObject(RemoteObject[SpotifyAPI], metaclass=ABCMeta):
    """Generic base class for Spotify-stored objects. Extracts key data from a Spotify API JSON response."""

    __slots__ = ()

    @property
    def id(self):
        return self.response["id"]

    @property
    def uri(self):
        return self.response["uri"]

    @property
    def has_uri(self):
        return not self.response.get("is_local", False)

    @property
    def url(self):
        return URL(self.response["href"])

    @property
    def url_ext(self):
        url = self.response["external_urls"].get("spotify")
        return URL(url) if url else None

    def _check_type(self) -> None:
        """
        Checks the given response is compatible with this object type, raises an exception if not.

        :raise RemoteObjectTypeError: When the response type is not compatible with this object.
        """
        required_keys = {"id", "uri", "href", "external_urls"}
        for key in required_keys:
            if key not in self.response:
                raise RemoteError(f"Response does not contain all required keys: {required_keys}")

        kind = self.__class__.__name__.removeprefix("Spotify").lower()
        if self.response.get("type") != kind:
            kind = RemoteObjectType.from_name(kind)[0]
            raise RemoteObjectTypeError("Response type invalid", kind=kind, value=self.response.get("type"))


class SpotifyItem(SpotifyObject, RemoteItem, metaclass=ABCMeta):
    """Generic base class for Spotify-stored items. Extracts key data from a Spotify API JSON response."""

    __slots__ = ()
