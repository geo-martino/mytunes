"""
Implements endpoints for getting items from the Spotify API.
"""
import re
from abc import ABCMeta
from collections.abc import Collection, Mapping, MutableMapping
from copy import copy
from itertools import batched
from typing import Any

from aiorequestful.types import URLInput
from yarl import URL

from musify.libraries.remote.core import RemoteResponse
from musify.libraries.remote.core.exception import APIError, RemoteObjectTypeError
from musify.libraries.remote.core.types import APIInputValueMulti, RemoteIDType, RemoteObjectType
from musify.libraries.remote.spotify.api.base import SpotifyAPIBase
from musify.utils import limit_value, to_collection

try:
    from tqdm.auto import tqdm
except ImportError:
    tqdm = None
ARTIST_ALBUM_TYPES = {"album", "single", "compilation", "appears_on"}


class SpotifyAPIItems(SpotifyAPIBase, metaclass=ABCMeta):

    __slots__ = ()

    _bar_threshold = 5

    def _get_unit(self, key: str | None = None, kind: str | None = None) -> str:
        """Determine the unit type to use in the progress bar"""
        if kind is None:
            kind = re.sub(r"[-_]+", " ", key) if key is not None else self.items_key
        return kind.lower().rstrip("s") + "s"

    ###########################################################################
    ## GET helpers: Generic methods for getting items
    ###########################################################################
    async def _get_items(
            self,
            url: URLInput,
            id_list: Collection[str],
            params: MutableMapping[str, Any] | None = None,
            key: str | None = None,
            kind: str | None = None,
            limit: int = 50,
    ) -> list[dict[str, Any]]:
        """
        Get responses from a given ``url`` appending an ID to each request from a given ``id_list``
        i.e. ``URL`` or ``ID``.

        When limit == 1, this function executes each URL request individually for each ID i.e. ``URL`` or ``ID``.
        Otherwise, it executes each URL request in batches of IDs based on the given ``limit`` size.
        It passes this chunked list of IDs to the request handler as a set of params in the form:
        ``{<ids>: '<comma separated string of IDs>'}``

        :param url: The base API URL endpoint for the required requests.
        :param id_list: List of IDs to append to the given URL.
        :param params: Extra parameters to add to each request.
        :param kind: The unit to use for logging. If None, determine from ``key`` or default to ``items``.
        :param key: The key to reference from each response to get the list of required values.
        :param limit: Size of each batch of IDs to get. This value will be limited to be between ``1`` and ``50``.
            When limit is 1, requests will be made individually without any batching params configured.
        :return: API JSON responses for each item at the given ``key``.
        :raise APIError: When the given ``key`` is not in the API response.
        """
        method = "GET"
        url = url.rstrip("/")
        kind = self._get_unit(key=key, kind=kind)
        params = params if params is not None else {}

        results, ids_cached, ids_not_cached = await self._get_responses_from_cache(
            method=method, url=url, id_list=id_list
        )

        if limit == 1:
            id_requests = ids_not_cached
        else:
            id_requests = list(batched(ids_not_cached, limit_value(limit, floor=1, ceil=50)))

        async def _get_result(i: int, id_: str | list[str]) -> dict[str, Any]:
            nonlocal params

            if isinstance(id_, str):  # single call
                href = f"{url}/{id_}"
                log = f"{kind.title()}: {len(ids_not_cached):>5}"
            else:  # batched call
                href = url
                params |= {"ids": ",".join(id_)}
                log = f"{kind.title() + ':':<11} {sum(map(len, id_requests[i:])):>6}/{len(ids_not_cached):<6}"

            response = await self.handler.request(
                method=method, url=href, params=params, persist=False, log_message=log
            )
            if key and key not in response:
                raise APIError(f"Given key {key!r} not found in response keys: {list(response.keys())}")

            if key:  # ensure identifiers are on each response so results can be sorted after execution
                for i, r in zip(id_, response[key], strict=True):
                    self._enrich_with_identifiers(response=r, id_=i, href=f"{url}/{i}")
            else:
                self._enrich_with_identifiers(response=response, id_=id_, href=f"{url}/{id_}")

            return response

        responses = await self.logger.get_asynchronous_iterator(
            (_get_result(i=i, id_=id_) for i, id_ in enumerate(id_requests)),
            desc=f"Getting {kind}",
            unit=kind if limit == 1 else "pages",
            disable=len(id_requests) < self._bar_threshold
        )
        if key:
            responses = [r for response in responses for r in response[key]]

        await self._cache_responses(method=method, responses=responses)

        id_list = tuple(id_list.keys()) if isinstance(id_list, Mapping) else to_collection(id_list)
        results.extend(responses)
        results.sort(key=lambda r: id_list.index(r[self.id_key]))

        return results

    async def extend_items(
            self,
            response: MutableMapping[str, Any] | RemoteResponse,
            kind: RemoteObjectType | str | None = None,
            key: RemoteObjectType | None = None,
            leave_bar: bool | None = None,
    ) -> list[dict[str, Any]]:
        """
        Extend the items for a given API ``response``.
        The function requests each page of the collection returning a list of all items
        found across all pages for this URL.

        Updates the value of the ``items`` key in-place by extending the value of the ``items`` key with new results.

        If a cache has been configured for this API, will also persist the items in any collection to the cache.

        If a :py:class:`RemoteResponse`, this function will not refresh it with the new response.
        The user must call `refresh` manually after execution.

        :param response: A remote API JSON response for an items type endpoint
            or a response/RemoteResponse which contains this response.
            Must include required keys:
            ``total`` and either ``next`` or ``href``, plus optional keys ``previous``, ``limit``, ``items`` etc.
        :param kind: The type of response being extended.
            If a RemoteObjectType is given, the method will attempt to enrich the items given
            and returned with given response on the key associated with this kind. The function will only do this
            if a parent response has been given and not an items block response.
        :param key: The type of response of the child objects. Used when selecting nested data for certain responses
            (e.g. user's followed artists).
        :param leave_bar: When a progress bar is displayed,
            toggle whether this bar should continue to be displayed after the operation is finished.
            When None, allow the logger to decide this setting.
        :return: API JSON responses for each item
        """
        if isinstance(response, RemoteResponse):
            response = response.response
        if not response:
            return []

        method = "GET"

        parent_key = kind
        parent_response = copy(response)

        key = self._format_key(key)
        response = response.get(key, response)
        if self.items_key not in response:
            response[self.items_key] = []

        if len(response[self.items_key]) == response["total"]:  # skip on fully extended response
            url = URL(response[self.url_key]).with_query(None)
            self.handler.log("SKIP", url, message="Response already extended")

            self._enrich_with_parent_response(
                response=response, key=key, parent_key=parent_key, parent_response=parent_response
            )
            return [item for item in response[self.items_key] if item]

        initial_url_key = "next" if response[self.items_key] and response.get("next") else self.url_key
        if not response.get(initial_url_key):
            return []

        initial_url = URL(response[initial_url_key])
        limit = int(initial_url.query.get("limit", 50))
        offset = int(initial_url.query.get("offset", len(response.get(self.items_key, []))))
        total = int(response["total"])

        urls = []
        for offset in range(offset, total, limit):
            params = dict(initial_url.query)
            params |= {"limit": limit, "offset": offset}
            urls.append(initial_url.with_query(params))

        async def _get_result(request: URL) -> dict[str, Any]:
            count = min(int(request.query["offset"]) + int(request.query["limit"]), response["total"])
            log = f"{count:>6}/{response["total"]:<6} {key or self.items_key}"
            r = await self.handler.request(method=method, url=request, log_message=log)
            return r.get(key, r)

        kind_name = self._format_key(kind) or self.items_key
        pages = (response["total"] - len(response[self.items_key])) / (response.get("limit", 1) or 1)
        results: list[dict[str, Any]] = await self.logger.get_asynchronous_iterator(
            map(_get_result, urls),
            initial=len(response[self.items_key]),
            total=response["total"],
            desc=f"Extending {kind_name}".rstrip("s") if kind_name[0].islower() else kind_name,
            unit=key or self.items_key,
            leave=leave_bar,
            disable=pages < self._bar_threshold,
        )
        results.sort(key=lambda r: r.get("offset", 0))  # tqdm doesn't execute in order, sort results

        # assign block values to response from last result
        final_result = next(reversed(results))
        response[self.url_key] = final_result[self.url_key]
        response["offset"] = final_result.get("offset")
        response["next"] = final_result.get("next")
        response["previous"] = final_result.get("previous")

        # assign results back to original response and enrich the child items
        response[self.items_key].extend(item for result in results for item in result[self.items_key])
        response[self.items_key] = [item for item in response[self.items_key] if item]
        self._enrich_with_parent_response(
            response=response, key=key, parent_key=parent_key, parent_response=parent_response
        )

        # cache child items
        key = key.rstrip("s") if key else key
        results_to_cache = [
            result[key] if key and key in result else result for result in response[self.items_key]
        ]
        await self._cache_responses(method=method, responses=results_to_cache)

        return response[self.items_key]

    ###########################################################################
    ## Core GET endpoint methods
    ###########################################################################
    async def get_items(
            self,
            values: APIInputValueMulti[RemoteResponse],
            kind: RemoteObjectType | None = None,
            limit: int = 50,
            extend: bool = True,
    ) -> list[dict[str, Any]]:
        """
        ``GET: /{kind}s`` - Get information for given ``values``.

        ``values`` may be:
            * A string representing a URL/URI/ID.
            * A MutableSequence of strings representing URLs/URIs/IDs of the same type.
            * A remote API JSON response for a collection including:
                - some items under an ``items`` key,
                - a valid ID value under an ``id`` key,
                - a valid item type value under a ``type`` key if ``kind`` is None.
            * A MutableSequence of remote API JSON responses for a collection including the same structure as above.
            * A RemoteResponse of the appropriate type for this RemoteAPI which holds a valid API JSON response
              as described above.
            * A Sequence of RemoteResponses as above.

        If JSON response(s) given, this update each response given by merging with the new response
        and replacing the ``items`` with the new results.

        If :py:class:`RemoteResponse` values are given, this function will call `refresh` on them.

        :param values: The values representing some remote objects. See description for allowed value types.
            These items must all be of the same type of item i.e. all tracks OR all artists etc.
        :param kind: Item type if given string is ID.
        :param limit: When requests can be batched, size of batches to request.
            This value will be limited to be between ``1`` and ``50`` or ``20`` if getting albums.
        :param extend: When True and the given ``kind`` is a collection of items,
            extend the response to include all items in this collection.
        :return: API JSON responses for each item.
        :raise RemoteObjectTypeError: Raised when the function cannot determine the item type
            of the input ``values``. Or when it does not recognise the type of the input ``values`` parameter.
        """
        # input validation
        if not isinstance(values, RemoteResponse) and not values:  # skip on empty
            url = f"{self.url}/{self._format_key(kind)}" if kind else self.url
            self.handler.log("SKIP", url, message="No data given")
            return []
        if kind is None:  # determine the item type
            kind = self.wrangler.get_item_type(values)
        else:
            self.wrangler.validate_item_type(values, kind=kind)

        unit = self._format_key(kind)
        url = f"{self.url}/{unit}"
        id_list = self.wrangler.extract_ids(values, kind=kind)

        if kind in {RemoteObjectType.USER, RemoteObjectType.PLAYLIST} or len(id_list) <= 1:
            limit = 1  # force non-batched calls
        elif kind == RemoteObjectType.ALBUM:
            limit = limit_value(limit, floor=1, ceil=20)
        results = await self._get_items(
            url=url, id_list=id_list, kind=unit, key=unit if limit > 1 else None, limit=limit
        )

        key = self.collection_item_map.get(kind, kind)
        key_name = self._format_key(key)
        if len(results) == 0 or any(key_name not in result for result in results) or not extend:
            self._merge_results_to_input(original=values, responses=results, ordered=True)
            self._refresh_responses(responses=values, skip_checks=False)
            self.handler.log("DONE", url, message=f"Retrieved {len(results):>6} {unit}")
            return results

        async def _get_result(result: dict[str, Any]) -> None:
            self.handler.log("INFO", url, message=f"Extending {key_name} on {unit}")
            await self.extend_items(result, kind=kind, key=key, leave_bar=False)

        await self.logger.get_asynchronous_iterator(
            map(_get_result, results),
            desc=f"Extending {unit}",
            unit=unit,
            disable=len(id_list) < self._bar_threshold
        )

        self._merge_results_to_input(original=values, responses=results, ordered=True)
        self._refresh_responses(responses=values, skip_checks=False)

        item_count = sum(len(result[key_name][self.items_key]) for result in results)
        self.handler.log("DONE", url, message=f"Retrieved {item_count:>6} {key_name} across {len(results):>5} {unit}")

        return results

    async def get_user_items(
            self,
            user: str | None = None,
            kind: RemoteObjectType = RemoteObjectType.PLAYLIST,
            limit: int = 50,
    ) -> list[dict[str, Any]]:
        """
        ``GET: /{kind}s`` - Get saved items for a given user.

        :param user: The ID of the user to get playlists for. If None, use the currently authenticated user.
        :param kind: Item type to retrieve for the user.
            Spotify only supports ``PLAYLIST`` types for non-authenticated users.
        :param limit: Size of each batch of items to request in the collection items request.
            This value will be limited to be between ``1`` and ``50``.
        :return: API JSON responses for each collection.
        :raise RemoteIDTypeError: Raised when the input ``user`` does not represent a user URL/URI/ID.
        :raise RemoteObjectTypeError: Raised a user is given and the ``kind`` is not ``PLAYLIST``.
            Or when the given ``kind`` is not a valid collection.
        """
        # input validation
        if kind not in self.user_item_types:
            raise RemoteObjectTypeError(f"{kind.name.title()}s are not a valid user collection type", kind=kind)
        if kind != RemoteObjectType.PLAYLIST and user is not None:
            raise RemoteObjectTypeError(
                f"Only able to retrieve {kind.name.lower()}s from the currently authenticated user",
                kind=kind
            )

        params = {"limit": limit_value(limit, floor=1, ceil=50)}
        if user is not None:
            url = self.wrangler.convert(user, kind=RemoteObjectType.USER, type_out=RemoteIDType.URL)
            url = f"{url}/{kind.name.lower()}s"
            desc_qualifier = "user's"
        elif kind == RemoteObjectType.ARTIST:
            url = f"{self.url}/me/following"
            desc_qualifier = "current user's followed"
            params["type"] = "artist"
        else:
            url = f"{self.url}/me/{kind.name.lower()}s"
            desc_qualifier = "current user's" if kind == RemoteObjectType.PLAYLIST else "current user's saved"

        desc = f"Getting {desc_qualifier} {kind.name.lower()}s"
        initial = await self.handler.get(url, params=params)
        results = await self.extend_items(initial, kind=desc, key=kind)

        self.handler.log("DONE", url, message=f"Retrieved {len(results):>6} {kind.name.lower()}s")

        return results

    ###########################################################################
    ## Tracks GET endpoint methods
    ###########################################################################
    async def get_tracks(
            self,
            values: APIInputValueMulti[RemoteResponse],
            features: bool = False,
            analysis: bool = False,
            limit: int = 50,
            *_,
            **__,
    ) -> list[dict[str, Any]]:
        """
        ``GET: /{kind}s`` + ``GET: /audio-features`` and/or ``GET: /audio-analysis``

        Get track(s) info and any audio features/analysis.
        Mostly just a wrapper for ``get_items`` and ``extend_tracks`` functions.

        ``values`` may be:
            * A string representing a URL/URI/ID of type 'track'.
            * A MutableSequence of strings representing URLs/URIs/IDs of the type 'track'.
            * A remote API JSON response for a track including:
                - some items under an ``items`` key,
                - a valid ID value under an ``id`` key.
            * A MutableSequence of remote API JSON responses for a set of tracks including the same structure as above.
            * A RemoteResponse of the appropriate type for this RemoteAPI which holds a valid API JSON response
              as described above.
            * A Sequence of RemoteResponses as above.

        If JSON response(s) given, this updates each response given by adding the results
        under the ``audio_features`` and ``audio_analysis`` keys as appropriate.

        :param values: The values representing some remote track/s. See description for allowed value types.
        :param features: When True, get audio features.
        :param analysis: When True, get audio analysis.
        :param limit: Size of batches to request when getting audio features.
            This value will be limited to be between ``1`` and ``50``.
        :return: API JSON responses for each item, or the original response if the input ``values`` are API responses.
        :raise RemoteObjectTypeError: Raised when the item types of the input ``values`` are not all tracks or IDs.
        """
        tracks = await self.get_items(values=values, kind=RemoteObjectType.TRACK, limit=limit)

        # ensure that response are being assigned back to the original values if API response(s) given
        if isinstance(values, Mapping | RemoteResponse):
            tracks = [values]
        elif isinstance(values, Collection) and all(isinstance(v, Mapping | RemoteResponse) for v in values):
            tracks = values

        await self.extend_tracks(values=tracks, features=features, analysis=analysis, limit=limit)
        return tracks

    async def extend_tracks(
            self,
            values: APIInputValueMulti[RemoteResponse],
            features: bool = False,
            analysis: bool = False,
            limit: int = 50,
    ) -> list[dict[str, Any]]:
        """
        ``GET: /audio-features`` and/or ``GET: /audio-analysis`` - Get audio features/analysis for given track/s.

        ``values`` may be:
            * A string representing a URL/URI/ID of type 'track'.
            * A MutableSequence of strings representing URLs/URIs/IDs of the type 'track'.
            * A remote API JSON response for a track including:
                - some items under an ``items`` key,
                - a valid ID value under an ``id`` key.
            * A MutableSequence of remote API JSON responses for a set of tracks including the same structure as above.
            * A RemoteResponse of the appropriate type for this RemoteAPI which holds a valid API JSON response
              as described above.
            * A Sequence of RemoteResponses as above.

        If JSON response(s) given, this updates each response given by adding the results
        under the ``audio_features`` and ``audio_analysis`` keys as appropriate.

        If :py:class:`RemoteResponse` values are given, this function will call `refresh` on them.

        :param values: The values representing some remote track/s. See description for allowed value types.
        :param features: When True, get audio features.
        :param analysis: When True, get audio analysis.
        :param limit: Size of batches to request when getting audio features.
            This value will be limited to be between ``1`` and ``50``.
        :return: API JSON responses for each item.
            Mapped to ``audio_features`` and ``audio_analysis`` keys as appropriate.
        :raise RemoteObjectTypeError: Raised when the item types of the input ``values`` are not all tracks or IDs.
        """
        # input validation
        if not features and not analysis:  # skip on all False
            return []
        if not values:  # skip on empty
            self.handler.log("SKIP", self.url, message="No data given")
            return []
        self.wrangler.validate_item_type(values, kind=RemoteObjectType.TRACK)

        id_list = self.wrangler.extract_ids(values, kind=RemoteObjectType.TRACK)

        # value list takes the form [URL, key, batched]
        config: dict[str, tuple[str, str, bool]] = {}
        if features:
            config["features"] = (f"{self.url}/audio-features", "audio_features", True)
        if analysis:
            config["analysis"] = (f"{self.url}/audio-analysis", "audio_analysis", False)

        async def _get_result(kind: str, url: str, key: str, batch: bool) -> dict[str, list[dict[str, Any]]]:
            _key = key
            _limit = limit
            if not batch or len(id_list) <= 1:
                _key = None
                _limit = 1

            return {key: await self._get_items(url=url, id_list=id_list, kind=kind, key=_key, limit=_limit)}

        results: list[dict[str, Any]] = []
        bar = self.logger.get_asynchronous_iterator(
            (_get_result(kind=kind, url=url, key=key, batch=batch) for kind, (url, key, batch) in config.items()),
            disable=True,
        )
        for result_map in await bar:
            for key, responses in result_map.items():
                responses.sort(key=lambda response: id_list.index(response[self.id_key]))
                responses = ({self.id_key: response[self.id_key], key: response} for response in responses)
                results = list(responses) if not results \
                    else [rs | rp for rs, rp in zip(results, responses, strict=True)]

        self._merge_results_to_input(original=values, responses=results, ordered=False, clear=False)
        self._refresh_responses(responses=values, skip_checks=False)

        def map_key(value: str) -> str:
            """Map the given ``value`` to logging appropriate string"""
            return value.replace("_", " ").replace("analysis", "analyses")

        log_types = " and ".join(map_key(key) for _, key, _ in config.values())
        self.handler.log(
            method="DONE",
            url=f"{self.url}/{"+".join(c[0].split("/")[-1] for c in config.values())}",
            message=f"Retrieved {log_types} for {len(id_list):>5} tracks"
        )

        return results

    ###########################################################################
    ## Artists GET endpoints methods
    ###########################################################################
    async def get_artist_albums(
            self, values: APIInputValueMulti[RemoteResponse], types: Collection[str] = (), limit: int = 50,
    ) -> dict[str, list[dict[str, Any]]]:
        """
        ``GET: /artists/{ID}/albums`` - Get all albums associated with the given artist/s.

        ``values`` may be:
            * A string representing a URL/URI/ID of type 'artist'.
            * A MutableSequence of strings representing URLs/URIs/IDs of the type 'artist'.
            * A remote API JSON response for an artist including a valid ID value under an ``id`` key.
            * A MutableSequence of remote API JSON responses for a set of artists including the same structure as above.
            * A RemoteResponse of the appropriate type for this RemoteAPI which holds a valid API JSON response
              as described above.
            * A Sequence of RemoteResponses as above.

        If JSON response(s) given, this updates each response given by adding the results under the ``albums`` key.

        If :py:class:`RemoteResponse` values are given, this function will call `refresh` on them.

        :param values: The values representing some remote artist/s. See description for allowed value types.
        :param types: The types of albums to return. Select from ``{"album", "single", "compilation", "appears_on"}``.
        :param limit: Size of batches to request.
            This value will be limited to be between ``1`` and ``50``.
        :return: A map of the Artist ID to a list of the API JSON responses for each album.
        :raise RemoteObjectTypeError: Raised when the item types of the input ``values`` are not all artists or IDs.
        """
        url = f"{self.url}/artists/{{id}}/albums"

        # input validation
        if not isinstance(values, RemoteResponse) and not values:  # skip on empty
            self.handler.log("SKIP", url, message="No data given")
            return {}

        if types and not all(t in ARTIST_ALBUM_TYPES for t in types):
            raise APIError(
                f"Given types not recognised, must be one or many of the following: {ARTIST_ALBUM_TYPES} ({types})"
            )
        self.wrangler.validate_item_type(values, kind=RemoteObjectType.ARTIST)

        params = {"limit": limit_value(limit, floor=1, ceil=50)}
        if types:
            params["include_groups"] = ",".join(set(types))

        key = RemoteObjectType.ALBUM
        results: dict[str, dict[str, Any]] = {}

        async def _get_result(id_: str) -> None:
            results[id_] = await self.handler.get(url=url.format(id=id_), params=params)
            await self.extend_items(results[id_], kind="artist albums", key=key, leave_bar=False)

        id_list = self.wrangler.extract_ids(values, kind=RemoteObjectType.ARTIST)
        await self.logger.get_asynchronous_iterator(
            map(_get_result, id_list),
            desc="Getting artist albums",
            unit="artist",
            disable=len(id_list) < self._bar_threshold
        )

        for result in results.values():  # add skeleton items block to album responses
            for album in result[self.items_key]:
                album["tracks"] = {
                    self.url_key: self.format_next_url(
                        url=str(URL(album[self.url_key]).with_query(None)) + "/tracks", offset=0, limit=50
                    ),
                    "total": album["total_tracks"]
                }

        results_remapped = [{self.id_key: id_, "albums": result} for id_, result in results.items()]
        self._merge_results_to_input(original=values, responses=results_remapped, ordered=False, clear=False)
        self._refresh_responses(responses=values, skip_checks=True)

        item_count = sum(map(len, results.values()))
        self.handler.log(
            method="DONE",
            url=url.format(id="..."),
            message=f"Retrieved {item_count:>6} albums across {len(results):>5} artists",
        )

        return {k: v[self.items_key] for k, v in results.items()}
