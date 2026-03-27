import re
from abc import ABCMeta, abstractmethod
from collections.abc import Mapping
from typing import Any, ContextManager

from aiohttp import ClientResponse
from aiorequestful.types import URLInput
from aioresponses import aioresponses
from aioresponses.core import RequestCall
from yarl import URL

from musify.libraries.remote.core.types import RemoteIDType, RemoteObjectType

ALL_ID_TYPES = RemoteIDType.all()
ALL_ITEM_TYPES = RemoteObjectType.all()


class RemoteMock(aioresponses, ContextManager, metaclass=ABCMeta):
    """Generates responses and sets up Remote API requests mock"""

    range_start = 25
    range_stop = 50
    range_max = 200

    limit_lower = 10
    limit_upper = 20
    limit_max = 50

    requests: dict[tuple[str, URL], list[RequestCall]]
    _responses: list[ClientResponse]

    def __enter__(self):
        super().__enter__()
        self.setup_mock()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        super().__exit__(exc_type, exc_val, exc_tb)

    @property
    @abstractmethod
    def item_type_map(self) -> dict[RemoteObjectType, list[dict[str, Any]]]:
        """Map of :py:class:`RemoteObjectType` to the mocked items mapped as ``{<ID>: <item>}``"""
        raise NotImplementedError

    @property
    @abstractmethod
    def item_type_map_user(self) -> dict[RemoteObjectType, list[dict[str, Any]]]:
        """Map of :py:class:`RemoteObjectType` to the mocked user items mapped as ``{<ID>: <item>}``"""
        raise NotImplementedError

    @abstractmethod
    def setup_mock(self):
        """Driver to set up mock responses for all endpoints"""
        raise NotImplementedError

    @property
    def total_requests(self) -> int:
        """Returns the total number of requests made to this mock."""
        return sum(map(len, self.requests.values()))

    def reset(self) -> None:
        """Reset the log for the history of requests and responses for by this mock. Does not reset matches."""
        self.requests.clear()
        self._responses.clear()

    @staticmethod
    def calculate_pages(limit: int, total: int) -> int:
        """
        Calculates the numbers of a pages that need to be called from a given ``total`` and ``limit`` per page
        to get all items related to this response.
        """
        if limit > 0 and total > 0:
            return total // limit + (total % limit > 0)  # round up
        return 0

    @abstractmethod
    def calculate_pages_from_response(self, response: Mapping[str, Any]) -> int:
        """
        Calculates the numbers of a pages that need to be called for a given ``response``
        to get all items related to this response.
        """
        raise NotImplementedError

    async def get_requests(
            self,
            method: str | None = None,
            url: URLInput | re.Pattern[str] | None = None,  # matches given after params have been stripped
            params: dict[str, Any] | None = None,
            response: dict[str, Any] | None = None
    ) -> list[tuple[URL, RequestCall, ClientResponse | None]]:
        """Get a get request from the history from the given URL and params"""
        results: list[tuple[URL, RequestCall]] = []
        for (request_method, request_url), requests in self.requests.items():
            for request in requests:
                matches = [
                    self._get_match_from_method(actual=request_method, expected=method),
                    self._get_match_from_url(actual=request_url, expected=url),
                    self._get_match_from_params(actual=request, expected=params),
                    await self._get_match_from_expected_response(actual=request_url, expected=response),
                ]
                if all(matches):
                    results.append((request_url, request))

        return [(url, request, self._get_response_from_url(url=url)) for url, request in results]

    @staticmethod
    def _get_match_from_method(actual: str, expected: str | None = None) -> bool:
        match = expected is None
        if not match:
            match = actual.upper() == expected.upper()

        return match

    @staticmethod
    def _get_match_from_url(actual: URLInput, expected: URLInput | re.Pattern[str] | None = None) -> bool:
        match = expected is None
        if not match:
            actual = str(URL(actual).with_query(None))
            if isinstance(expected, URLInput):
                match = actual == str(URL(expected).with_query(None))
            elif isinstance(expected, re.Pattern):
                match = bool(expected.search(actual))

        return match

    @staticmethod
    def _get_match_from_params(actual: RequestCall, expected: dict[str, Any] | None = None) -> bool:
        match = expected is None
        if not match and (request_params := actual.kwargs.get("params")):
            for k, v in request_params.items():
                if k in expected and str(expected[k]) != v:
                    break
                match = True

        return match

    async def _get_match_from_expected_response(
            self, actual: URLInput, expected: dict[str, Any] | None = None
    ) -> bool:
        match = expected is None
        if not match:
            response = self._get_response_from_url(url=actual)
            if response is None:
                return match

            payload = await response.json()
            for k, v in payload.items():
                if k in expected and str(expected[k]) != str(v):
                    break
                match = True

        return match

    def _get_response_from_url(self, url: URLInput) -> ClientResponse | None:
        response = None
        for response in self._responses:
            if str(response.url) == url:
                break

        return response
