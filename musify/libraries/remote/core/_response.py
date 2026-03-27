"""
Just the core abstract class for the :py:mod:`Remote` module.
Placed here separately to avoid circular import logic issues.
"""
from abc import ABCMeta, abstractmethod
from typing import Any

from yarl import URL

from musify.base import MusifyObject


class RemoteResponse(MusifyObject, metaclass=ABCMeta):

    __slots__ = ()

    # noinspection PyPropertyDefinition,PyMethodParameters
    @property
    @abstractmethod
    def kind(cls):
        """The type of remote object this class represents"""
        raise NotImplementedError

    @property
    @abstractmethod
    def response(self) -> dict[str, Any]:
        """The API response for this object"""
        raise NotImplementedError

    @property
    @abstractmethod
    def id(self) -> str:
        """The ID of this item/collection."""
        raise NotImplementedError

    @property
    @abstractmethod
    def url(self) -> URL:
        """The API URL of this item/collection."""
        raise NotImplementedError

    @property
    @abstractmethod
    def url_ext(self) -> URL | None:
        """The external URL of this item/collection."""
        raise NotImplementedError

    @abstractmethod
    def refresh(self, skip_checks: bool = False) -> None:
        """
        Refresh this object by updating from the stored API response.
        Useful for updating stored variables after making changes to the stored API response manually.
        """
        raise NotImplementedError
