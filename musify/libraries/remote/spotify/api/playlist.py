"""
Implements endpoints for manipulating playlists with the Spotify API.
"""
from abc import ABCMeta
from collections.abc import Sequence, Mapping
from itertools import batched
from typing import Any

from yarl import URL

from musify import PROGRAM_NAME, PROGRAM_URL
from musify.libraries.remote.core import RemoteResponse
from musify.libraries.remote.core.exception import APIError, RemoteIDTypeError
from musify.libraries.remote.core.types import APIInputValueSingle, RemoteIDType, RemoteObjectType
from musify.libraries.remote.spotify.api.base import SpotifyAPIBase
from musify.utils import limit_value


class SpotifyAPIPlaylists(SpotifyAPIBase, metaclass=ABCMeta):
    """API endpoints for processing collections i.e. playlists, albums, shows, and audiobooks"""

    __slots__ = ()

    async def load_user_playlists(self) -> None:
        """Load and store user playlists data for the currently authorised user in this API object"""
        responses = await self.get_user_items(kind=RemoteObjectType.PLAYLIST)
        self.user_playlist_data = {response["name"]: response for response in responses}

    async def get_playlist_url(self, playlist: APIInputValueSingle[RemoteResponse]) -> URL:
        """
        Determine the type of the given ``playlist`` and return its API URL.
        If type cannot be determined, attempt to find the playlist in the
        list of the currently authorised user's loaded playlists.

        If you find this method is giving unexpected results when giving the name of a playlist.
        You may reload the currently loaded user's playlists by calling :py:meth:`load_user_playlists`

        :param playlist: One of the following to identify the playlist URL:
            - playlist URL/URI/ID,
            - the name of the playlist in the current user's playlists,
            - the API response of a playlist.
            - a RemoteResponse object representing a remote playlist.
        :return: The playlist URL.
        :raise RemoteIDTypeError: Raised when the function cannot determine the item type of
            the input ``playlist``. Or when it does not recognise the type of the input ``playlist`` parameter.
        """
        if isinstance(playlist, RemoteResponse):
            playlist = playlist.response

        if isinstance(playlist, Mapping):
            if self.url_key in playlist:
                url = playlist[self.url_key]
            elif self.id_key in playlist:
                url = self.wrangler.convert(
                    playlist[self.id_key],
                    kind=RemoteObjectType.PLAYLIST,
                    type_in=RemoteIDType.ID,
                    type_out=RemoteIDType.URL
                )
            elif "uri" in playlist:
                url = self.wrangler.convert(
                    playlist["uri"],
                    kind=RemoteObjectType.PLAYLIST,
                    type_in=RemoteIDType.URI,
                    type_out=RemoteIDType.URL
                )
            else:
                raise APIError(f"Could not determine URL from given input: {playlist}")

            return URL(url)

        try:
            url = self.wrangler.convert(playlist, kind=RemoteObjectType.PLAYLIST, type_out=RemoteIDType.URL)
        except RemoteIDTypeError:
            if not self.user_playlist_data:
                await self.load_user_playlists()

            if playlist not in self.user_playlist_data:
                raise RemoteIDTypeError(
                    "Given playlist is not a valid URL/URI/ID and name not found in user's playlists",
                    value=playlist
                )

            url = self.user_playlist_data[playlist][self.url_key]

        return URL(url)

    ###########################################################################
    ## POST endpoints
    ###########################################################################
    async def create_playlist(
            self, name: str, public: bool = True, collaborative: bool = False, *_, **__
    ) -> dict[str, Any]:
        """
        ``POST: /users/{user_id}/playlists`` - Create an empty playlist for the current user with the given name.

        :param name: Name of playlist to create.
        :param public: Set playlist availability as `public` if True and `private` if False.
        :param collaborative: Set playlist to collaborative i.e. other users may edit the playlist.
        :return: API JSON response for the created playlist.
        """
        url = f"{self.url}/users/{self.user_id}/playlists"

        body = {
            "name": name,
            "description": f"Generated using {PROGRAM_NAME}: {PROGRAM_URL}",
            "public": public,
            "collaborative": collaborative,
        }
        response = (await self.handler.post(url, json=body))
        name = response["name"]
        url = response[self.url_key]
        self.user_playlist_data[name] = response

        # response from creating playlist gives back incorrect user info on 'owner' key, fix it
        response["owner"]["display_name"] = self.user_name
        response["owner"][self.id_key] = self.user_id
        response["owner"]["uri"] = self.wrangler.convert(
            self.user_id, kind=RemoteObjectType.USER, type_in=RemoteIDType.ID, type_out=RemoteIDType.URI
        )
        response["owner"][self.url_key] = self.wrangler.convert(
            self.user_id, kind=RemoteObjectType.USER, type_in=RemoteIDType.ID, type_out=RemoteIDType.URL
        )
        response["owner"]["external_urls"][self.source.lower()] = self.wrangler.convert(
            self.user_id, kind=RemoteObjectType.USER, type_in=RemoteIDType.ID, type_out=RemoteIDType.URL_EXT
        )

        self.handler.log("DONE", url, message=f"Created playlist: {name!r} -> {url}")
        return response

    async def add_to_playlist(
            self,
            playlist: APIInputValueSingle[RemoteResponse],
            items: Sequence[str],
            limit: int = 100,
            skip_dupes: bool = True
    ) -> int:
        """
        ``POST: /playlists/{playlist_id}/tracks`` - Add list of tracks to a given playlist.

        :param playlist: One of the following to identify the playlist to add to:
            - playlist URL/URI/ID,
            - the name of the playlist in the current user's playlists,
            - the API response of a playlist.
            - a RemoteResponse object representing a remote playlist.
        :param items: List of URLs/URIs/IDs of the tracks to add.
        :param limit: Size of each batch of IDs to add. This value will be limited to be between ``1`` and ``100``.
        :param skip_dupes: Skip duplicates.
        :return: The number of tracks added to the playlist.
        :raise RemoteIDTypeError: Raised when the input ``playlist`` does not represent
            a playlist URL/URI/ID.
        :raise RemoteObjectTypeError: Raised when the item types of the input ``items``
            are not all tracks or IDs.
        """
        url = f"{await self.get_playlist_url(playlist)}/tracks"

        if len(items) == 0:
            self.handler.log("SKIP", url, message="No data given")
            return 0

        self.wrangler.validate_item_type(items, kind=RemoteObjectType.TRACK)

        uri_list = [
            self.wrangler.convert(item, kind=RemoteObjectType.TRACK, type_out=RemoteIDType.URI) for item in items
        ]
        if skip_dupes:  # skip tracks currently in playlist
            pl_current = next(iter(await self.get_items(url, kind=RemoteObjectType.PLAYLIST)))
            tracks_key = self.collection_item_map[RemoteObjectType.PLAYLIST].name.lower() + "s"
            tracks = pl_current[tracks_key][self.items_key]

            uri_current = [track["track"]["uri"] for track in tracks]
            uri_list = [uri for uri in uri_list if uri not in uri_current]

        limit = limit_value(limit, floor=1, ceil=100)
        for uris in batched(uri_list, limit):  # add tracks in batches
            await self.handler.post(url, json={"uris": uris}, log_message=f"Adding {len(uris):>6} items")

        self.handler.log("DONE", url, message=f"Added {len(uri_list):>6} items to playlist: {url}")
        return len(uri_list)

    ###########################################################################
    ## PUT endpoints
    ###########################################################################
    async def follow_playlist(self, playlist: APIInputValueSingle[RemoteResponse], *args, **kwargs) -> URL:
        url = URL(f"{await self.get_playlist_url(playlist)}/followers")
        await self.handler.put(url)
        return url

    ###########################################################################
    ## DELETE endpoints
    ###########################################################################
    async def delete_playlist(self, playlist: APIInputValueSingle[RemoteResponse]) -> URL:
        """
        ``DELETE: /playlists/{playlist_id}/followers`` - Unfollow a given playlist.
        WARNING: This function will destructively modify your remote playlists.

        :param playlist: One of the following to identify the playlist to delete:
            - playlist URL/URI/ID,
            - the name of the playlist in the current user's playlists,
            - the API response of a playlist.
            - a RemoteResponse object representing a remote playlist.
        :return: API URL for playlist.
        """
        url = URL(f"{await self.get_playlist_url(playlist)}/followers")
        await self.handler.delete(url)
        return url

    async def clear_from_playlist(
            self,
            playlist: APIInputValueSingle[RemoteResponse],
            items: Sequence[str] | None = None,
            limit: int = 100
    ) -> int:
        """
        ``DELETE: /playlists/{playlist_id}/tracks`` - Clear tracks from a given playlist.
        WARNING: This function can destructively modify your remote playlists.

        :param playlist: One of the following to identify the playlist to clear from :
            - playlist URL/URI/ID,
            - the name of the playlist in the current user's playlists,
            - the API response of a playlist.
            - a RemoteResponse object representing a remote playlist.
        :param items: List of URLs/URIs/IDs of the tracks to remove. If None, clear all songs from the playlist.
        :param limit: Size of each batch of IDs to clear in a single request.
            This value will be limited to be between ``1`` and ``100``.
        :return: The number of tracks cleared from the playlist.
        :raise RemoteIDTypeError: Raised when the input ``playlist`` does not represent
            a playlist URL/URI/ID.
        :raise RemoteObjectTypeError: Raised when the item types of the input ``items``
            are not all tracks or IDs.
        """
        url = f"{await self.get_playlist_url(playlist)}/tracks"
        if items is not None and len(items) == 0:
            self.handler.log("SKIP", url, message="No data given")
            return 0

        if items is None:  # clear everything
            pl_current = next(iter(await self.get_items(url, kind=RemoteObjectType.PLAYLIST, extend=True)))

            tracks_key = self.collection_item_map[RemoteObjectType.PLAYLIST].name.lower() + "s"
            tracks = pl_current[tracks_key][self.items_key]
            uri_list = [track[tracks_key.rstrip("s")]["uri"] for track in tracks]
        else:  # clear only the items given
            self.wrangler.validate_item_type(items, kind=RemoteObjectType.TRACK)
            uri_list = [
                self.wrangler.convert(item, kind=RemoteObjectType.TRACK, type_out=RemoteIDType.URI) for item in items
            ]

        if not uri_list:  # skip when nothing to clear
            self.handler.log("SKIP", url, message="No tracks to clear")
            return 0

        async def _delete_batch(batch: list[str]) -> None:
            body = {"tracks": [{"uri": uri} for uri in batch]}
            await self.handler.delete(url,  json=body, log_message=f"Clearing {len(uri_list):>3} tracks")

        limit = limit_value(limit, floor=1, ceil=100)
        await self.logger.get_asynchronous_iterator(map(_delete_batch, batched(uri_list, limit)), disable=True)

        self.handler.log("DONE", url, message=f"Cleared {len(uri_list):>3} tracks")
        return len(uri_list)
