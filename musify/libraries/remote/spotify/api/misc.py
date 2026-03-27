"""
Implements all required non-items and non-playlist endpoints from the Spotify API.
"""
import logging
from abc import ABCMeta
from collections.abc import MutableMapping
from typing import Any

from aiorequestful.types import Number

from musify.libraries.remote.core.types import RemoteIDType, RemoteObjectType
from musify.libraries.remote.spotify.api.base import SpotifyAPIBase
from musify.utils import limit_value


class SpotifyAPIMisc(SpotifyAPIBase, metaclass=ABCMeta):

    __slots__ = ()

    async def print_collection(
            self,
            value: str | MutableMapping[str, Any] | None = None,
            kind: RemoteIDType | None = None,
            limit: int = 20,
    ) -> None:
        if not value:  # get user to paste in URL/URI
            value = input("\33[1mEnter URL/URI/ID: \33[0m")
        if not kind:
            kind = self.wrangler.get_item_type(value)
        key = self.collection_item_map[kind].name.lower()

        while kind is None:  # get user to input ID type
            kind = RemoteObjectType.from_name(input("\33[1mEnter ID type: \33[0m"))[0]

        id_ = self.wrangler.extract_ids(values=value, kind=kind)[0]
        url = self.wrangler.convert(id_, kind=kind, type_in=RemoteIDType.ID, type_out=RemoteIDType.URL)
        limit = limit_value(limit, floor=1, ceil=50)

        name = (await self.handler.get(url, params={"limit": limit}))["name"]
        response = await self.handler.get(f"{url}/{key}s", params={"limit": limit})

        i = 0
        while response.get("next") or i < response["total"]:  # loop through each page, printing data in blocks of 20
            if response.get("offset", 0) == 0:  # first page, show header
                url_ext = self.wrangler.convert(id_, kind=kind, type_in=RemoteIDType.ID, type_out=RemoteIDType.URL_EXT)
                self.logger.print_message(
                    f"\n\33[96mShowing tracks for {kind.name.lower()}\33[0m: "
                    f"\33[94m{name} \33[97m- {url_ext} \33[0m\n"
                )

            tracks = [item[key] if key in item else item for item in response[self.items_key]]
            for i, track in enumerate(tracks, i + 1):  # print each item in this page
                if isinstance(track["duration_ms"], Number):
                    length = track["duration_ms"] / 1000
                else:
                    length = track["duration_ms"]["totalMilliseconds"] / 1000
                self.print_item(i=i, name=track["name"], uri=track["uri"], length=length, total=response["total"])

            if response["next"]:
                response = await self.handler.get(response["next"], params={"limit": limit})
            self.logger.print_message()

    ###########################################################################
    ## GET endpoints
    ###########################################################################
    async def get_self(self, update_user_data: bool = True) -> dict[str, Any]:
        """
        ``GET: /me`` - Get API response for information on current user.

        :param update_user_data: When True, update the ``_user_data`` stored in this API object.
        """
        r = await self.handler.get(url=f"{self.url}/me")
        if update_user_data:
            self.user_data = r
        return r

    async def query(self, query: str | None, kind: RemoteObjectType, limit: int = 10) -> list[dict[str, Any]]:
        """
        ``GET: /search`` - Query for items. Modify result types returned with kind parameter

        :param query: Search query.
        :param kind: The remote object type to search for.
        :param limit: Number of results to get and return.
        :return: The response from the endpoint.
        """
        if not query or len(query) > 150:  # query is too short or too long, skip
            return []

        url = f"{self.url}/search"
        params = {'q': query, "type": kind.name.lower(), "limit": limit_value(limit, floor=1, ceil=50)}
        response = await self.handler.get(url, params=params)

        if "error" in response:
            self.handler.log("SKIP", url, message=[f"Query: {query}", response['error']], level=logging.ERROR)
            return []

        results = response[f"{kind.name.lower()}s"][self.items_key]
        if kind not in self.collection_item_map:
            return results

        key = self.collection_item_map[kind].name.lower() + "s"
        totals_key = {
            RemoteObjectType.ALBUM: "total_tracks",
            RemoteObjectType.SHOW: "total_episodes",
            RemoteObjectType.AUDIOBOOK: "total_chapters"
        }
        for result in results:
            if key in result and self.url_key in result[key] and "total" in result[key]:
                continue

            href = self.format_next_url(f"{result[self.url_key]}/{key}", limit=50)
            result[key] = {self.url_key: href, "total": result.get(totals_key.get(kind), 0)}

        return results
