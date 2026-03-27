"""
The framework for interacting with a remote API.

All methods that interact with the API should return raw, unprocessed responses.
"""
import logging
from abc import ABCMeta, abstractmethod
from collections.abc import Collection, MutableMapping, Mapping, Sequence, Iterable
from typing import Any, Self

from aiorequestful.auth import Authoriser
from aiorequestful.cache.backend.base import ResponseCache
from aiorequestful.cache.exception import CacheError
from aiorequestful.cache.session import CachedSession
from aiorequestful.request import RequestHandler
from aiorequestful.response.payload import JSONPayloadHandler
from aiorequestful.types import UnitSequence, UnitList, ImmutableJSON, JSON
from yarl import URL

from musify.libraries.remote.core import RemoteResponse
from musify.libraries.remote.core.types import APIInputValueSingle, APIInputValueMulti, RemoteIDType, RemoteObjectType
from musify.libraries.remote.core.wrangle import RemoteDataWrangler
from musify.logger import MusifyLogger
from musify.utils import align_string, to_collection


class RemoteAPI[A: Authoriser](metaclass=ABCMeta):
    """
    Collection of endpoints for a remote API.
    See :py:class:`RequestHandler` and :py:class:`Authoriser`
    for more info on which params to pass to authorise and execute requests.

    :param wrangler: The :py:class:`RemoteDataWrangler` for this API type.
    :param authoriser: The authoriser to use when authorising requests to the API.
    :param cache: When given, attempt to use this cache for certain request types before calling the API.
        Repository and cachable request types can be set up by child classes.
    """

    __slots__ = ("logger", "handler", "wrangler", "user_data", "user_playlist_data")

    #: Map of :py:class:`RemoteObjectType` for remote collections
    #: to the  :py:class:`RemoteObjectType` of the items they hold
    collection_item_map = {
        RemoteObjectType.PLAYLIST: RemoteObjectType.TRACK,
        RemoteObjectType.ALBUM: RemoteObjectType.TRACK,
        RemoteObjectType.AUDIOBOOK: RemoteObjectType.CHAPTER,
        RemoteObjectType.SHOW: RemoteObjectType.EPISODE,
    }
    #: A set of possible saved item types that can be retrieved for the currently authenticated user
    user_item_types = (
            set(collection_item_map) | {RemoteObjectType.TRACK, RemoteObjectType.ARTIST, RemoteObjectType.EPISODE}
    )
    #: The key to use when getting an ID from a response
    id_key = "id"
    #: The key to use when getting the URL from a response
    url_key = "href"

    @property
    @abstractmethod
    def user_id(self) -> str | None:
        """ID of the currently authorised user"""
        raise NotImplementedError

    @property
    @abstractmethod
    def user_name(self) -> str | None:
        """Name of the currently authorised user"""
        raise NotImplementedError

    @property
    def url(self) -> URL:
        """The base URL of the API"""
        return self.wrangler.url_api

    @property
    def source(self) -> str:
        """The name of the API service"""
        return self.wrangler.source

    def __init__(self, authoriser: A, wrangler: RemoteDataWrangler, cache: ResponseCache | None = None):
        # noinspection PyTypeChecker
        #: The :py:class:`MusifyLogger` for this  object
        self.logger: MusifyLogger = logging.getLogger(__name__)

        #: A :py:class:`RemoteDataWrangler` object for processing URIs
        self.wrangler = wrangler

        #: The :py:class:`RequestHandler` for handling authorised requests to the API
        self.handler: RequestHandler[A, JSON] = RequestHandler.create(
            authoriser=authoriser, cache=cache, payload_handler=JSONPayloadHandler(indent=2),
        )

        #: Stores the loaded user data for the currently authorised user
        self.user_data: dict[str, Any] = {}
        #: Stores the loaded user playlists data for the currently authorised user
        self.user_playlist_data: dict[str, dict[str, Any]] = {}

    async def __aenter__(self) -> Self:
        await self.handler.__aenter__()

        try:
            await self._setup_cache()
        except CacheError:
            pass

        session = self.handler.session
        if isinstance(session, CachedSession):
            for repository in session.cache.values():
                # all repositories must use the same payload handler as the request handler
                # for it to function correctly
                repository.settings.payload_handler = self.handler.payload_handler

        await self.load_user()
        await self.load_user_playlists()

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.handler.__aexit__(exc_type, exc_val, exc_tb)

    @abstractmethod
    async def _setup_cache(self) -> None:
        """Set up the repositories and repository getter on the self.handler.session's cache."""
        raise NotImplementedError

    async def authorise(self) -> Self:
        """
        Main method for authorisation, tests/refreshes/reauthorises as needed

        :return: Self.
        :raise APIError: If the token cannot be validated.
        """
        await self.handler.authorise()
        return self

    async def close(self) -> None:
        """Close the current session. No more requests will be possible once this has been called."""
        await self.handler.close()

    ###########################################################################
    ## Misc helpers
    ###########################################################################
    async def load_user(self) -> None:
        """Load and store user data for the currently authorised user in this API object"""
        self.user_data = await self.get_self()

    @abstractmethod
    async def load_user_playlists(self) -> None:
        """Load and store user playlists data for the currently authorised user in this API object"""
        raise NotImplementedError

    @staticmethod
    def _merge_results_to_input_mapping(
            original: MutableMapping[str, Any], response: Mapping[str, Any], clear: bool = True,
    ) -> None:
        if clear:
            original.clear()
        original |= response

    def _merge_results_to_input(
            self,
            original: UnitSequence[ImmutableJSON] | UnitSequence[RemoteResponse],
            responses: UnitList[ImmutableJSON],
            ordered: bool = True,
            clear: bool = True,
    ) -> None:
        """
        If API response type given on input, update with new results.
        Assumes on a one-to-one relationship between ``original`` and the list of ``results``.

        :param original: The original values given to the function.
        :param responses: The new results from the API.
        :param ordered: When True, function assumes the order of items in ``original`` and ``results`` is the same.
            When False, the function will attempt to match each input value to each result by matching on
            the ``id`` key of each dictionary.
        :param ordered: When True, clear the original value before merging, completely replacing all original data.
        """
        if isinstance(original, str) or not isinstance(original, Collection | RemoteResponse):
            return

        if isinstance(original, RemoteResponse):
            original = [original]
        elif not isinstance(original, Sequence):
            original = to_collection(original)
        if not isinstance(responses, Sequence):
            responses = to_collection(responses, list)

        original = [item.response if isinstance(item, RemoteResponse) else item for item in original]

        valid_types_input = all(isinstance(item, MutableMapping) for item in original)
        valid_types_responses = all(isinstance(item, MutableMapping) for item in responses)
        valid_lengths = len(original) == len(responses)
        if not all((valid_types_input, valid_types_responses, valid_lengths)):
            self.logger.debug(
                "Could not merge responses to given user input | "
                "Reason: assertions failed | "
                f"{valid_types_input=} {valid_types_responses=} {valid_lengths=} | "
            )
            return

        if not ordered:
            expected_keys_input = all(self.id_key in item for item in original)
            expected_keys_responses = all(self.id_key in item for item in responses)
            if not all((expected_keys_input, expected_keys_responses)):
                self.logger.debug(
                    "Could not merge responses to given user input | "
                    f"Reason: unordered and cannot order on {self.id_key=} | "
                    f"{expected_keys_input=} {expected_keys_responses=}"
                )
                return

            id_ordered = [response[self.id_key] for response in original]
            responses.sort(key=lambda response: id_ordered.index(response[self.id_key]))

        for item, response in zip(original, responses):
            self._merge_results_to_input_mapping(original=item, response=response, clear=clear)

    @staticmethod
    def _refresh_responses(responses: Any, skip_checks: bool = False) -> None:
        if isinstance(responses, RemoteResponse):
            responses = [responses]
        if not isinstance(responses, Iterable) or not any(isinstance(r, RemoteResponse) for r in responses):
            return

        for response in responses:
            if isinstance(response, RemoteResponse):
                response.refresh(skip_checks=skip_checks)

    def print_item(
            self, i: int, name: str, uri: str, length: float = 0, total: int = 1, max_width: int = 50
    ) -> None:
        """
        Pretty print item data for displaying to the user.
        Format = ``<i> - <name> | <length> | <URI> - <URL>``.

        :param i: The position of this item in the collection.
        :param name: The name of the item.
        :param uri: The URI of the item.
        :param length: The duration of the item in seconds.
        :param total: The total number of items in the collection
        :param max_width: The maximum width to print names as. Any name lengths longer than this will be truncated.
        """
        self.logger.print_message(
            f"\33[92m{str(i).zfill(len(str(total)))} \33[0m- "
            f"\33[97m{align_string(name, max_width=max_width)} \33[0m| "
            f"\33[91m{str(int(length // 60)).zfill(2)}:{str(round(length % 60)).zfill(2)} \33[0m| "
            f"\33[93m{uri} \33[0m- "
            f"{self.wrangler.convert(uri, type_in=RemoteIDType.URI, type_out=RemoteIDType.URL_EXT)}"
        )

    @abstractmethod
    async def print_collection(
            self,
            value: APIInputValueSingle[RemoteResponse] | None = None,
            kind: RemoteIDType | None = None,
            limit: int = 20,
    ) -> None:
        """
        Pretty print collection data for displaying to the user.
        Runs :py:meth:`print_item()` for each item in the collection.

        ``value`` may be:
            * A string representing a URL/URI/ID.
            * A remote API JSON response for a collection with a valid ID value under an ``id`` key.
            * A RemoteResponse representing some remote collection of items.

        :param value: The value representing some remote collection. See description for allowed value types.
        :param kind: When an ID is provided, give the kind of ID this is here.
            If None and ID is given, user will be prompted to give the kind anyway.
        :param limit: The number of results to call per request and,
            therefore, the number of items in each printed block.
        """
        raise NotImplementedError

    @abstractmethod
    async def get_playlist_url(self, playlist: APIInputValueSingle[RemoteResponse]) -> URL:
        """
        Determine the type of the given ``playlist`` and return its API URL.
        If type cannot be determined, attempt to find the playlist in the
        list of the currently authenticated user's playlists.

        :param playlist: In URL/URI/ID form, or the name of one of the currently authenticated user's playlists.
        :return: The playlist URL.
        :raise RemoteIDTypeError: Raised when the function cannot determine the item type of
            the input ``playlist``. Or when it does not recognise the type of the input ``playlist`` parameter.
        """
        raise NotImplementedError

    ###########################################################################
    ## Core - GET endpoints
    ###########################################################################
    @abstractmethod
    async def get_self(self, update_user_data: bool = True) -> dict[str, Any]:
        """
        ``GET`` - Get API response for information on current user

        :param update_user_data: When True, update the ``_user_data`` stored in this API object."""
        raise NotImplementedError

    @abstractmethod
    async def query(self, query: str, kind: RemoteObjectType, limit: int = 10) -> list[dict[str, Any]]:
        """
        ``GET`` - Query for items. Modify result types returned with kind parameter

        :param query: Search query.
        :param kind: The remote object type to search for.
        :param limit: Number of results to get and return.
        :return: The response from the endpoint.
        """
        raise NotImplementedError

    ###########################################################################
    ## Item - GET endpoints
    ###########################################################################
    @abstractmethod
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

        If a :py:class:`RemoteResponse`, this function will not refresh it with the new response.
        The user must call `refresh` manually after execution.

        :param response: A remote API JSON response for an items type endpoint.
        :param kind: The type of response being extended. Optional, used only for logging.
        :param key: The type of response of the child objects.
        :param leave_bar: When a progress bar is displayed,
            toggle whether this bar should continue to be displayed after the operation is finished.
            When None, allow the logger to decide this setting.
        :return: API JSON responses for each item
        """
        raise NotImplementedError

    @abstractmethod
    async def get_items(
            self,
            values: APIInputValueMulti[RemoteResponse],
            kind: RemoteObjectType | None = None,
            limit: int = 50,
            extend: bool = True,
    ) -> list[dict[str, Any]]:
        """
        ``GET`` - Get information for given ``values``.

        ``values`` may be:
            * A string representing a URL/URI/ID.
            * A MutableSequence of strings representing URLs/URIs/IDs of the same type.
            * A remote API JSON response for a collection.
            * A MutableSequence of remote API JSON responses for a collection.
            * A RemoteResponse of the appropriate type for this RemoteAPI which holds a valid API JSON response
              as described above.
            * A Sequence of RemoteResponses as above.

        If JSON response(s) given, this updates each response given by merging with the new response.

        If :py:class:`RemoteResponse` values are given, this function will call `refresh` on them.

        :param values: The values representing some remote objects. See description for allowed value types.
            These items must all be of the same type of item i.e. all tracks OR all artists etc.
        :param kind: Item type if given string is ID.
        :param limit: When requests can be batched, size of batches to request.
            This value will be limited to be between ``1`` and ``50``.
        :param extend: When True and the given ``kind`` is a collection of items,
            extend the response to include all items in this collection.
        :return: API JSON responses for each item.
        :raise RemoteObjectTypeError: Raised when the function cannot determine the item type
            of the input ``values``. Or when it does not recognise the type of the input ``values`` parameter.
        """
        raise NotImplementedError

    @abstractmethod
    async def get_tracks(
            self, values: APIInputValueMulti[RemoteResponse], limit: int = 50, *args, **kwargs
    ) -> list[dict[str, Any]]:
        """
        Wrapper for :py:meth:`get_items` which only returns Track type responses.
        See :py:meth:`get_items` for more info.
        """
        raise NotImplementedError

    @abstractmethod
    async def get_user_items(
            self, user: str | None = None, kind: RemoteObjectType = RemoteObjectType.PLAYLIST, limit: int = 50,
    ) -> list[dict[str, Any]]:
        """
        ``GET`` - Get saved items for a given user.

        :param user: The ID of the user to get playlists for. If None, use the currently authenticated user.
        :param kind: Item type to retrieve for the user.
        :param limit: Size of each batch of items to request in the collection items request.
            This value will be limited to be between ``1`` and ``50``.
        :return: API JSON responses for each collection.
        :raise RemoteIDTypeError: Raised when the input ``user`` does not represent a user URL/URI/ID.
        :raise RemoteObjectTypeError: When the given ``kind`` is not a valid user item/collection.
        """
        raise NotImplementedError

    ###########################################################################
    ## Playlist specific endpoints
    ###########################################################################
    @abstractmethod
    async def create_playlist(self, name: str, *args, **kwargs) -> dict[str, Any]:
        """
        ``POST`` - Create an empty playlist for the current user with the given name.

        :param name: Name of playlist to create.
        :return: API JSON response for the created playlist.
        """
        raise NotImplementedError

    @abstractmethod
    async def add_to_playlist(
            self,
            playlist: APIInputValueSingle[RemoteResponse],
            items: Sequence[str],
            limit: int = 50,
            skip_dupes: bool = True
    ) -> int:
        """
        ``POST`` - Add list of tracks to a given playlist.

        :param playlist: One of the following to identify the playlist to clear:
            - playlist URL/URI/ID,
            - the name of the playlist in the current user's playlists,
            - the API response of a playlist.
            - a RemoteResponse object representing a remote playlist.
        :param items: List of URLs/URIs/IDs of the tracks to add.
        :param limit: Size of each batch of IDs to add. This value will be limited to be between ``1`` and ``50``.
        :param skip_dupes: Skip duplicates.
        :return: The number of tracks added to the playlist.
        :raise RemoteIDTypeError: Raised when the input ``playlist`` does not represent
            a playlist URL/URI/ID.
        :raise RemoteObjectTypeError: Raised when the item types of the input ``items``
            are not all tracks or IDs.
        """
        raise NotImplementedError

    async def get_or_create_playlist(self, name: str, *args, **kwargs) -> dict[str, Any]:
        """
        Attempt to find the playlist with the given ``name`` and return it.
        Otherwise, create a new playlist.

        Any given args and kwargs are passed directly onto :py:meth:`create_playlist`
        when a matching loaded playlist is not found.

        When a playlist is created, persist the response back to the loaded playlists in this object.

        :param name: The case-sensitive name of the playlist to get/create.
        :return: API JSON response for the loaded/created playlist.
        """
        if not self.user_playlist_data:
            await self.load_user_playlists()

        response = self.user_playlist_data.get(name)
        if response:
            return response

        return await self.create_playlist(name, *args, **kwargs)

    async def follow_playlist(self, playlist: APIInputValueSingle[RemoteResponse], *args, **kwargs) -> URL:
        """
        ``PUT`` - Follow a given playlist.

        :param playlist: One of the following to identify the playlist to clear:
            - playlist URL/URI/ID,
            - the name of the playlist in the current user's playlists,
            - the API response of a playlist.
            - a RemoteResponse object representing a remote playlist.
        :return: API URL for playlist.
        """
        raise NotImplementedError

    @abstractmethod
    async def delete_playlist(self, playlist: APIInputValueSingle[RemoteResponse]) -> URL:
        """
        ``DELETE`` - Unfollow/delete a given playlist.
        WARNING: This function will destructively modify your remote playlists.

        :param playlist: One of the following to identify the playlist to clear:
            - playlist URL/URI/ID,
            - the name of the playlist in the current user's playlists,
            - the API response of a playlist.
            - a RemoteResponse object representing a remote playlist.
        :return: API URL for playlist.
        """
        raise NotImplementedError

    @abstractmethod
    async def clear_from_playlist(
            self,
            playlist: APIInputValueSingle[RemoteResponse],
            items: Collection[str] | None = None,
            limit: int = 100
    ) -> int:
        """
        ``DELETE`` - Clear tracks from a given playlist.
        WARNING: This function can destructively modify your remote playlists.

        :param playlist: One of the following to identify the playlist to clear:
            - playlist URL/URI/ID,
            - the name of the playlist in the current user's playlists,
            - the API response of a playlist.
            - a RemoteResponse object representing a remote playlist.
        :param items: List of URLs/URIs/IDs of the tracks to remove. If None, clear all songs from the playlist.
        :param limit: Size of each batch of IDs to clear in a single request.
            This value will be limited to be between ``1`` and ``100``.
        :return: The number of tracks cleared from the playlist.
        :raise RemoteIDTypeError: Raised when the input ``playlist`` does not represent a playlist URL/URI/ID.
        :raise RemoteObjectTypeError: Raised when the item types of the input ``items``
            are not all tracks or IDs.
        """
        raise NotImplementedError
