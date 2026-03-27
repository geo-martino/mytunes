"""
Base functionality to be shared by all classes that implement :py:class:`RemoteAPI` functionality for Spotify.
"""
from abc import ABCMeta
from collections.abc import Collection, MutableMapping, Iterable
from typing import Any

from aiorequestful.auth.oauth2 import AuthorisationCodeFlow
from aiorequestful.cache.backend.base import ResponseRepository
from aiorequestful.cache.exception import CacheError
from aiorequestful.cache.session import CachedSession
from aiorequestful.types import URLInput
from yarl import URL

from musify.libraries.remote.core.api import RemoteAPI
from musify.libraries.remote.core.types import RemoteObjectType


class SpotifyAPIBase(RemoteAPI[AuthorisationCodeFlow], metaclass=ABCMeta):
    """Base functionality required for all endpoint functions for the Spotify API"""

    __slots__ = ()

    #: The key to reference when extracting items from a collection
    items_key = "items"

    ###########################################################################
    ## Format values/responses
    ###########################################################################
    @staticmethod
    def _format_key(key: str | RemoteObjectType | None) -> str | None:
        """Get the expected key in a response from a :py:class:`RemoteObjectType`"""
        if key is None:
            return
        if isinstance(key, RemoteObjectType):
            key = key.name
        return key.lower().rstrip("s") + "s"

    @staticmethod
    def format_next_url(url: URLInput, offset: int = 0, limit: int = 20) -> str:
        """Format a `next` style URL for looping through API pages"""
        url = URL(url)

        params: dict[str, Any] = dict(url.query)
        params["offset"] = offset
        params["limit"] = limit

        url = url.with_query(params)
        return str(url)

    ###########################################################################
    ## Enrich/manipulate responses
    ###########################################################################
    def _enrich_with_identifiers(self, response: dict[str, Any], id_: str, href: str) -> None:
        """Ensure key identifiers are present in the response."""
        if self.id_key not in response:
            response[self.id_key] = id_
        if self.url_key not in response:
            response[self.url_key] = href

    def _enrich_with_parent_response(
            self,
            response: MutableMapping[str, Any],
            key: str,
            parent_key: str | RemoteObjectType | None,
            parent_response: MutableMapping[str, Any]
    ) -> None:
        """
        Some endpoints don't include parent response on child items.
        This method adds the given ``parent_response`` back to the child ``response`` on the given ``key``.
        """
        if (
                not parent_key
                or isinstance(parent_key, str)
                or parent_key == RemoteObjectType.PLAYLIST
                or self.items_key not in response
                or self.items_key in parent_response
        ):
            return

        parent_key_name = self._format_key(parent_key).rstrip("s")
        parent_response = {k: v for k, v in parent_response.items() if k != key}

        if not parent_response:
            return

        for item in response[self.items_key]:
            if parent_key_name not in item:
                item[parent_key_name] = parent_response

    ###########################################################################
    ## Cache utilities
    ###########################################################################
    async def _get_responses_from_cache(
            self, method: str, url: URLInput, id_list: Collection[str]
    ) -> tuple[list[dict[str, Any]], Collection[str], Collection[str]]:
        """
        Attempt to find the given ``id_list`` in the cache of the request handler and return results.

        :param url: The base API URL endpoint for the required requests.
        :param id_list: List of IDs to append to the given URL.
        :return: (Results from the cache, IDs found in the cache, IDs not found in the cache)
        """
        session = self.handler.session
        if not isinstance(session, CachedSession):
            self.handler.log("CACHE", url, message="Cache not configured, skipping...")
            return [], [], id_list

        repository = session.cache.get_repository_from_url(url=url)
        if repository is None:
            self.handler.log("CACHE", url, message="No repository for this endpoint, skipping...")
            return [], [], id_list

        results = await repository.get_responses([(method.upper(), id_,) for id_ in id_list])
        ids_found = {result[self.id_key] for result in results}
        ids_not_found = {id_ for id_ in id_list if id_ not in ids_found}

        self.handler.log(
            method="CACHE",
            url=url,
            message=[f"Retrieved {len(results):>6} cached responses", f"{len(ids_not_found):>6} not found in cache"]
        )
        return results, ids_found, ids_not_found

    async def _cache_responses(self, method: str, responses: Iterable[dict[str, Any]]) -> None:
        """Persist ``results`` of a given ``method`` to the cache."""
        session = self.handler.session
        if not isinstance(session, CachedSession) or not responses:
            return

        # take all parts of href path, excluding ID
        possible_urls = {"/".join(result.get(self.url_key, "").split("/")[:-1]) for result in responses}
        possible_urls = {url for url in possible_urls if url}
        if not possible_urls:
            return
        if len(possible_urls) > 1:
            raise CacheError(
                "Too many different types of results given. Given results must relate to the same repository type."
            )
        results_mapped = {(method.upper(), result[self.id_key]): result for result in responses}
        url = next(iter(possible_urls))
        repository: ResponseRepository = session.cache.get_repository_from_url(url)
        if repository is not None:
            self.handler.log(
                method="CACHE",
                url=url,
                message=f"Caching {len(results_mapped)} responses to {repository.settings.name!r} repository",
            )
            await repository.save_responses({k: await repository.serialize(v) for k, v in results_mapped.items()})
