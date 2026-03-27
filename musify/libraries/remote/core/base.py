"""
Core abstract classes for the :py:mod:`Remote` module.

These define the foundations of any remote object or item.
"""
from __future__ import annotations

from abc import ABCMeta, abstractmethod
from typing import Any, Self

from musify.base import MusifyItem
from musify.libraries.remote.core import RemoteResponse
from musify.libraries.remote.core.api import RemoteAPI
from musify.libraries.remote.core.exception import APIError
from musify.libraries.remote.core.types import APIInputValueSingle, RemoteObjectType


class RemoteObject[T: (RemoteAPI | None)](RemoteResponse, metaclass=ABCMeta):
    """
    Generic base class for remote objects. Extracts key data from a remote API JSON response.

    :param response: The remote API JSON response
    :param api: The instantiated and authorised API object for this source type.
    """

    __slots__ = ("_response", "api")
    __attributes_ignore__ = ("response", "api")

    @property
    @abstractmethod
    def uri(self) -> str:
        """URI (Uniform Resource Indicator) is the unique identifier for this item/collection."""
        raise NotImplementedError

    @property
    @abstractmethod
    def has_uri(self) -> bool:
        """Does this item/collection have a valid URI that is not a local URI."""
        raise NotImplementedError

    @property
    def response(self) -> dict[str, Any]:
        """The API response for this object"""
        return self._response

    # noinspection PyPropertyDefinition,PyMethodParameters
    @property
    @abstractmethod
    def kind(cls) -> RemoteObjectType:
        raise NotImplementedError

    def __init__(self, response: dict[str, Any], api: T = None, skip_checks: bool = False):
        super().__init__()
        self._response = response

        #: The :py:class:`RemoteAPI` to call when reloading
        self.api = api

        self._check_type()
        self.refresh(skip_checks=skip_checks)

    async def __aenter__(self) -> Self:
        await self.api.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.api.__aexit__(exc_type, exc_val, exc_tb)

    @abstractmethod
    def _check_type(self) -> None:
        """
        Checks the given response is compatible with this object type, raises an exception if not.

        :raise RemoteObjectTypeError: When the response type is not compatible with this object.
        """
        raise NotImplementedError

    def _check_for_api(self) -> None:
        """
        Checks the API has been set on the instance, raises an exception if not.

        :raise APIError: When the API has not been set for this instance.
        """
        if self.api is None:
            raise APIError("API is not set. Assign an API to this instance first.")

    @classmethod
    @abstractmethod
    async def load(
            cls, value: APIInputValueSingle[RemoteResponse], api: RemoteAPI, *args, **kwargs
    ) -> Self:
        """
        Generate a new object of this class,
        calling all required endpoints to get a complete set of data for this item type.

        ``value`` may be:
            * A string representing a URL/URI/ID.
            * A remote API JSON response for a collection with a valid ID value under an ``id`` key.
            * An object of the same type as this collection.
              The remote API JSON response will be used to load a new object.

        :param value: The value representing some remote object. See description for allowed value types.
        :param api: An authorised API object to load the object from.
        """
        raise NotImplementedError

    @abstractmethod
    async def reload(self, *args, **kwargs) -> None:
        """
        Reload this object from the API, calling all required endpoints
        to get a complete set of data for this item type.
        """
        raise NotImplementedError

    def __hash__(self):
        """Uniqueness of a remote object is its URI"""
        return hash(self.uri)

    def __eq__(self, item: RemoteObject):
        return self.uri == item.uri


class RemoteItem(RemoteObject, MusifyItem, metaclass=ABCMeta):
    """Generic base class for remote items. Extracts key data from a remote API JSON response."""

    __attributes_classes__ = (RemoteObject, MusifyItem)
