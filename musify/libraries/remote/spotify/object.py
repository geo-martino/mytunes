"""
Implements all :py:mod:`Remote` object types for Spotify.
"""
from __future__ import annotations

from abc import ABCMeta, abstractmethod
from collections.abc import Iterable, MutableMapping, Mapping, Collection
from copy import copy, deepcopy
from datetime import datetime
from typing import Any, Self

from aiorequestful.types import UnitCollection

from musify.libraries.remote.core import RemoteResponse
from musify.libraries.remote.core.object import RemoteCollectionLoader, RemoteTrack
from musify.libraries.remote.core.object import RemotePlaylist, RemoteAlbum, RemoteArtist
from musify.libraries.remote.core.types import APIInputValueSingle, RemoteIDType, RemoteObjectType
from musify.libraries.remote.spotify.api import SpotifyAPI
from musify.libraries.remote.spotify.base import SpotifyObject, SpotifyItem
from musify.libraries.remote.spotify.exception import SpotifyCollectionError
from musify.utils import to_collection


class SpotifyTrack(SpotifyItem, RemoteTrack):
    """
    Extracts key ``track`` data from a Spotify API JSON response.

    :param response: The Spotify API JSON response.
    """

    __slots__ = ("_disc_total", "_comments", "_artists")

    _song_keys = ("C", "C#/Db", "D", "D#/Eb", "E", "F", "F#/Gb", "G", "G#/Ab", "A", "A#/Bb", "B")

    @property
    def name(self):
        return self.title

    @property
    def title(self) -> str:
        return self.response["name"]

    @property
    def artist(self):
        artists = self.response.get("artists", {})
        artist = self.tag_sep.join(artist["name"] for artist in artists)
        return artist or None

    @property
    def artists(self) -> list[SpotifyArtist]:
        return self._artists

    @property
    def album(self):
        return self.response.get("album", {}).get("name")

    @property
    def album_artist(self):
        album = self.response.get("album", {})
        album_artist = self.tag_sep.join(artist["name"] for artist in album.get("artists", []))
        return album_artist or None

    @property
    def track_number(self) -> int:
        return self.response["track_number"]

    @property
    def track_total(self):
        return self.response.get("album", {}).get("total_tracks")

    @property
    def genres(self):
        """
        List of genres for the album this track is featured on.
        If not found, genres from the main artist are given.
        """
        album = self.response.get("album", {})
        if album.get("genres"):
            return [g.title() for g in album.get("genres")]

        artists = self.response.get("artists", {})
        if not artists:
            return

        main_artist_genres = artists[0].get("genres", [])
        return [g.title() for g in main_artist_genres] if main_artist_genres else None

    @property
    def year(self):
        album = self.response.get("album", {})
        if "release_date" not in album:
            return
        values = album["release_date"].split("-")
        return int(values[0]) if len(values) >= 1 and values[0].isdigit() else None

    @property
    def month(self):
        album = self.response.get("album", {})
        if "release_date" not in album or "release_date_precision" not in album:
            return
        if album["release_date_precision"] in {"year"}:
            # release date is not precise to month, do not return month even if it exists in the value
            return
        values = album["release_date"].split("-")
        return int(values[1]) if len(values) >= 2 and values[1].isdigit() else None

    @property
    def day(self):
        album = self.response.get("album", {})
        if "release_date" not in album or "release_date_precision" not in album:
            return
        if album["release_date_precision"] in {"year", "month"}:
            # release date is not precise to day, do not return day even if it exists in the value
            return
        values = album["release_date"].split("-")
        return int(values[2]) if len(values) >= 3 and values[2].isdigit() else None

    @property
    def bpm(self):
        if "audio_features" not in self.response:
            return
        return self.response["audio_features"]["tempo"]

    @property
    def key(self):
        if "audio_features" not in self.response:
            return

        # correctly formatted song key string
        key_value: int = self.response["audio_features"]["key"]
        key: str | None = self._song_keys[key_value] if key_value >= 0 else None
        is_minor: bool = self.response["audio_features"]["mode"] == 0

        if not key:
            return None
        elif '/' in key:
            key_sep = key.split('/')
            return f"{key_sep[0]}{'m'*is_minor}/{key_sep[1]}{'m'*is_minor}"
        else:
            return f"{key}{'m'*is_minor}"

    @property
    def disc_number(self) -> int:
        return self.response["disc_number"]

    @property
    def disc_total(self):
        return self._disc_total

    @disc_total.setter
    def disc_total(self, value: int | None):
        self._disc_total = value

    @property
    def compilation(self) -> bool:
        album = self.response.get("album", {})
        return album.get("album_type", "") == "compilation"

    @property
    def comments(self):
        return self._comments

    @comments.setter
    def comments(self, value: UnitCollection[str] | None):
        self._comments = [value] if isinstance(value, str) else to_collection(value, list)

    @property
    def image_links(self):
        album = self.response.get("album", {})
        if not (images := album.get("images", [])):
            return {}

        images = {image["height"]: image["url"] for image in images}
        return {"cover_front": next(url for height, url in images.items() if height == max(images))}

    @property
    def length(self):
        if isinstance(self.response["duration_ms"], Mapping):
            return self.response["duration_ms"]["totalMilliseconds"] / 1000
        return self.response["duration_ms"] / 1000

    @property
    def rating(self):
        return self.response.get("popularity")

    def __init__(self, response: dict[str, Any], api: SpotifyAPI | None = None, skip_checks: bool = False):
        self._disc_total = None
        self._comments = None

        self._artists: list[SpotifyArtist] | None = None

        if "track" in response and isinstance(response["track"], dict):
            # happens in 'user's saved ...' or playlist responses
            response = response["track"]

        super().__init__(response=response, api=api, skip_checks=skip_checks)

    def refresh(self, skip_checks: bool = False) -> None:
        self._artists = [
            SpotifyArtist(artist, api=self.api, skip_checks=skip_checks)
            for artist in self._response.get("artists", {})
        ]

    @classmethod
    async def load(
            cls,
            value: APIInputValueSingle[Self],
            api: SpotifyAPI,
            features: bool = False,
            analysis: bool = False,
            extend_album: bool = False,
            extend_artists: bool = False,
            *_,
            **__
    ) -> Self:
        self = cls.__new__(cls)
        self.api = api

        # set a mock response with URL to load from
        id_ = api.wrangler.extract_ids(value)[0]
        self._response = {
            "href": api.wrangler.convert(
                id_, kind=RemoteObjectType.TRACK, type_in=RemoteIDType.ID, type_out=RemoteIDType.URL
            )
        }
        await self.reload(
            features=features, analysis=analysis, extend_album=extend_album, extend_artists=extend_artists
        )

        return self

    async def reload(
            self,
            features: bool = False,
            analysis: bool = False,
            extend_album: bool = False,
            extend_artists: bool = False,
            *_,
            **__
    ) -> None:
        self._check_for_api()

        # reload with enriched data
        response = await self.api.handler.get(self.url)
        if extend_album:
            await self.api.get_items(response["album"], kind=RemoteObjectType.ALBUM, extend=False)
        if extend_artists:
            await self.api.get_items(response["artists"], kind=RemoteObjectType.ARTIST)
        if features or analysis:
            await self.api.extend_tracks(response, features=features, analysis=analysis)

        self.__init__(response=response, api=self.api)


class SpotifyCollectionLoader[T: SpotifyObject](RemoteCollectionLoader[T], SpotifyObject, metaclass=ABCMeta):
    """Generic class for storing a collection of Spotify objects that can be loaded from an API response."""

    __slots__ = ()

    @classmethod
    def _get_item_kind(cls, api: SpotifyAPI) -> RemoteObjectType:
        """Returns the :py:class:`RemoteObjectType` for the items in this collection"""
        return api.collection_item_map[cls.kind]

    @classmethod
    @abstractmethod
    async def _get_items(
            cls, items: Collection[str] | MutableMapping[str, Any], api: SpotifyAPI
    ) -> list[dict[str, Any]]:
        """Call the ``api`` to get values for the given ``items`` URIs"""
        raise NotImplementedError

    @classmethod
    def _filter_items(cls, items: Iterable[T], response: Mapping[str, Any]) -> Iterable[T]:
        """
        Filter down and return only ``items`` associated with the given ``response``.
        The default implementation of this will just return the given ``items``.
        Override for object-specific filtering.
        """
        return items

    @classmethod
    async def _extend_response(cls, response: MutableMapping[str, Any], api: SpotifyAPI, *_, **__) -> bool:
        """
        Apply extensions to specific aspects of the given ``response``.
        Does nothing by default. Override to implement object-specific extensions.

        :return: True if checks should be skipped when initialising the object.
        """
        pass

    @classmethod
    def _merge_items_to_response(
            cls,
            items: Iterable[T | Mapping[str, Any]],
            response: Iterable[MutableMapping[str, Any]],
            skip: Collection[str] = ()
    ) -> tuple[set[str], set[str]]:
        """
        Find items in the ``response`` that match from the given ``items`` and replace them in the response.
        Optionally, provide a list of URIs to ``skip``.

        :return: Two sets of URIs for items that could and could not be found in response.
        """
        items_mapped: dict[str, T | Mapping[str, Any]] = {
            item.uri if isinstance(item, SpotifyObject) else item["uri"]: item for item in items
        }
        uri_matched: set[str] = set()
        uri_missing: set[str] = set()

        # find items in the response that match from the given items
        for source_item in response:
            if cls.kind == RemoteObjectType.PLAYLIST:
                source_item = source_item["track"]

            if source_item["uri"] in skip:
                continue
            elif source_item["uri"] in items_mapped:
                # replace the skeleton response with the response from the given items
                replacement_item = items_mapped.pop(source_item["uri"])
                if isinstance(replacement_item, SpotifyObject):
                    replacement_item = replacement_item.response

                source_item.clear()
                source_item |= replacement_item
                uri_matched.add(source_item["uri"])
            elif not source_item.get("is_local"):  # add to missing list
                uri_missing.add(source_item["uri"])

        return uri_matched, uri_missing

    @classmethod
    async def _load_new(cls, value: APIInputValueSingle[Self], api: SpotifyAPI, *args, **kwargs) -> Self:
        """
        Sets up a new object of the current class for the given ``value`` by calling ``__new__``
        and adding just enough attributes to the object to get :py:meth:`reload` to run.
        """
        # noinspection PyTypeChecker
        id_ = next(iter(api.wrangler.extract_ids(values=value, kind=cls.kind)))
        # noinspection PyTypeChecker
        url = api.wrangler.convert(id_, kind=cls.kind, type_in=RemoteIDType.ID, type_out=RemoteIDType.URL)

        self = cls.__new__(cls)
        self.api = api
        self._response = {"href": url}

        await self.reload(*args, **kwargs)
        return self

    @classmethod
    async def load(
            cls,
            value: APIInputValueSingle[Self],
            api: SpotifyAPI,
            items: Iterable[T] = (),
            leave_bar: bool = True,
            *args,
            **kwargs
    ) -> Self:
        item_kind = cls._get_item_kind(api=api)
        item_key = item_kind.name.lower() + "s"

        if isinstance(value, RemoteResponse):
            value = value.response

        # no items given, regenerate API response from the URL
        if any({not items, isinstance(value, Mapping) and api.items_key not in value.get(item_key, [])}):
            return await cls._load_new(value=value, api=api, *args, **kwargs)

        if isinstance(value, MutableMapping) and api.wrangler.get_item_type(value) == cls.kind:  # input is response
            response = deepcopy(value)
        else:  # load fresh response from the API
            response = await cls.api.get_items(value, kind=cls.kind)[0]

        # filter down input items to those that match the response
        items = cls._filter_items(items=items, response=response)
        matched, missing = cls._merge_items_to_response(items=items, response=response[item_key][api.items_key])

        if missing:
            items_missing = await cls._get_items(items=missing, api=api)
            cls._merge_items_to_response(items=items_missing, response=response[item_key][api.items_key], skip=matched)

        skip_checks = await cls._extend_response(response=response, api=api, *args, **kwargs)
        return cls(response=response, api=api, skip_checks=skip_checks)


class SpotifyPlaylist(SpotifyCollectionLoader[SpotifyTrack], RemotePlaylist[SpotifyTrack]):
    """
    Extracts key ``playlist`` data from a Spotify API JSON response.

    :param response: The Spotify API JSON response
    """

    __slots__ = ("_tracks",)
    __attributes_ignore__ = ("date_added",)

    @staticmethod
    def _validate_item_type(items: Any | Iterable[Any]) -> bool:
        if isinstance(items, Iterable):
            return all(isinstance(item, SpotifyTrack) for item in items)
        return isinstance(items, SpotifyTrack)

    @property
    def name(self):
        return self.response["name"]

    @name.setter
    def name(self, value: str):
        self.response["name"] = value

    @property
    def description(self):
        return self.response["description"]

    @description.setter
    def description(self, value: str | None):
        self.response["description"] = value

    @property
    def public(self):
        """Can other users access this playlist"""
        return self.response["public"]

    @public.setter
    def public(self, value: bool):
        self.response["public"] = value
        if value and self.collaborative:
            self.collaborative = False

    @property
    def collaborative(self):
        """Are other users allowed to modify this playlist"""
        return self.response["collaborative"]

    @collaborative.setter
    def collaborative(self, value: bool):
        if value and self.public:
            raise SpotifyCollectionError("You can only set collaborative to true on non-public playlists.")
        self.response["collaborative"] = value

    @property
    def followers(self):
        return int(self.response["followers"]["total"])

    @property
    def owner_name(self):
        return self.response["owner"]["display_name"]

    @property
    def owner_id(self):
        return self.response["owner"]["id"]

    @property
    def tracks(self):
        return self._tracks

    @property
    def track_total(self):
        return self.response["tracks"]["total"]

    @property
    def image_links(self):
        if not (images := self.response.get("images")):
            return {}

        images = {image["height"]: image["url"] for image in images}
        return {"cover_front": url for height, url in images.items() if height == max(images)}

    @property
    def date_created(self):
        """:py:class:`datetime` object representing when the first track was added to this playlist"""
        return min(self.date_added.values()) if self.date_added else None

    @property
    def date_modified(self):
        """:py:class:`datetime` object representing when a track was most recently added/removed"""
        return max(self.date_added.values()) if self.date_added else None

    @property
    def date_added(self):
        return {
            track["track"]["uri"]: datetime.strptime(track["added_at"], "%Y-%m-%dT%H:%M:%SZ")
            for track in self.response["tracks"]["items"]
        }

    def __init__(self, response: dict[str, Any], api: SpotifyAPI | None = None, skip_checks: bool = False):
        self._tracks: list[SpotifyTrack] | None = None
        super().__init__(response=response, api=api, skip_checks=skip_checks)

    def refresh(self, skip_checks: bool = False) -> None:
        self._tracks = [
            SpotifyTrack(track, api=self.api, skip_checks=skip_checks)
            for track in self._response.get("tracks", {}).get("items", [])
        ]
        if not skip_checks:
            self._check_total()

    @classmethod
    async def _get_items(
            cls, items: Collection[str] | MutableMapping[str, Any], api: SpotifyAPI
    ) -> list[dict[str, Any]]:
        return await api.get_tracks(items)

    @classmethod
    async def _extend_response(
            cls,
            response: MutableMapping[str, Any],
            api: SpotifyAPI,
            leave_bar: bool = True,
            extend_tracks: bool = False,
            extend_features: bool = False,
            *_,
            **__
    ) -> bool:
        item_kind = api.collection_item_map[cls.kind]

        if extend_tracks:
            # noinspection PyTypeChecker
            await api.extend_items(response, kind=cls.kind, key=item_kind, leave_bar=leave_bar)

        item_key = item_kind.name.lower() + "s"
        tracks = [item["track"] for item in response.get(item_key, {}).get(api.items_key, [])]
        if tracks and extend_features:
            await api.extend_tracks(tracks, limit=response[item_key]["limit"], features=True)

        return not extend_tracks

    async def reload(self, extend_tracks: bool = False, extend_features: bool = False, *_, **__) -> None:
        self._check_for_api()
        response = next(iter(await self.api.get_items(self.url, kind=RemoteObjectType.PLAYLIST, extend=False)))

        skip_checks = await self._extend_response(
            response=response, api=self.api, extend_tracks=extend_tracks, extend_features=extend_features
        )

        self.__init__(response=response, api=self.api, skip_checks=skip_checks)

    def _get_track_uris_from_api_response(self) -> list[str]:
        return [track["track"]["uri"] for track in self.response["tracks"].get("items", [])]


class SpotifyAlbum(RemoteAlbum[SpotifyTrack], SpotifyCollectionLoader[SpotifyTrack]):
    """
    Extracts key ``album`` data from a Spotify API JSON response.

    :param response: The Spotify API JSON response
    """

    __slots__ = ("_tracks", "_artists")

    @staticmethod
    def _validate_item_type(items: Any | Iterable[Any]) -> bool:
        if isinstance(items, Iterable):
            return all(isinstance(item, SpotifyTrack) for item in items)
        return isinstance(items, SpotifyTrack)

    @property
    def name(self):
        return self.response["name"]

    @property
    def tracks(self) -> list[SpotifyTrack]:
        return self._tracks

    @property
    def artists(self) -> list[SpotifyArtist]:
        return self._artists

    @property
    def artist(self):
        return self.tag_sep.join(artist["name"] for artist in self.response["artists"])

    @property
    def album_artist(self):
        return self.artist

    @property
    def track_total(self):
        return self.response["total_tracks"]

    @property
    def genres(self):
        if "genres" in self.response:
            return [g.title() for g in self.response["genres"]]
        main_artist_genres = self.response["artists"][0].get("genres", [])
        return [g.title() for g in main_artist_genres] if main_artist_genres else None

    @property
    def year(self):
        values = self.response["release_date"].split("-")
        return int(values[0]) if len(values) >= 1 and values[0].isdigit() else None

    @property
    def month(self):
        if self.response["release_date_precision"] in {"year"}:
            # release date is not precise to month, do not return month even if it exists in the value
            return
        values = self.response["release_date"].split("-")
        return int(values[1]) if len(values) >= 2 and values[1].isdigit() else None

    @property
    def day(self):
        if self.response["release_date_precision"] in {"year", "month"}:
            # release date is not precise to day, do not return day even if it exists in the value
            return
        values = self.response["release_date"].split("-")
        return int(values[2]) if len(values) >= 3 and values[2].isdigit() else None

    @property
    def compilation(self):
        return self.response["album_type"] == "compilation"

    @property
    def image_links(self):
        if not (images := self.response.get("images")):
            return {}

        images = {image["height"]: image["url"] for image in images}
        return {"cover_front": url for height, url in images.items() if height == max(images)}

    @property
    def rating(self):
        return self.response.get("popularity")

    def __init__(self, response: dict[str, Any], api: SpotifyAPI | None = None, skip_checks: bool = False):
        self._tracks: list[SpotifyTrack] | None = None
        self._artists: list[SpotifyArtist] | None = None

        if "album" in response and isinstance(response["album"], dict):
            # happens in 'user's saved ...' or playlist responses
            response = response["album"]

        super().__init__(response=response, api=api, skip_checks=skip_checks)

    def refresh(self, skip_checks: bool = False) -> None:
        album_only = copy(self.response)
        album_only.pop("tracks", None)
        for track in self.response.get("tracks", {}).get("items", []):
            track["album"] = album_only

        self._artists = [SpotifyArtist(artist, api=self.api) for artist in self._response.get("artists", {})]
        self._tracks = [
            SpotifyTrack(artist, api=self.api) for artist in self.response.get("tracks", {}).get("items", [])
        ]
        if not skip_checks:
            self._check_total()

        for track in self.tracks:
            track.disc_total = self.disc_total

    @classmethod
    async def _get_items(
            cls, items: Collection[str] | MutableMapping[str, Any], api: SpotifyAPI
    ) -> list[dict[str, Any]]:
        return await api.get_tracks(items)

    @classmethod
    def _filter_items(cls, items: Iterable[SpotifyTrack], response: Mapping[str, Any]) -> Iterable[SpotifyTrack]:
        """Filter down and return only ``items`` the items associated with the given ``response``"""
        return [item for item in items if item.response.get("album", {}).get("id") == response["id"]]

    @classmethod
    async def _extend_response(
            cls,
            response: MutableMapping[str, Any],
            api: SpotifyAPI,
            leave_bar: bool = True,
            extend_tracks: bool = False,
            extend_artists: bool = False,
            extend_features: bool = False,
            *_,
            **__
    ) -> bool:
        item_kind = api.collection_item_map[cls.kind]

        if extend_artists:
            await api.get_items(response["artists"], kind=RemoteObjectType.ARTIST)

        if extend_tracks:
            # noinspection PyTypeChecker
            await api.extend_items(response, kind=cls.kind, key=item_kind, leave_bar=leave_bar)

        item_key = item_kind.name.lower() + "s"
        tracks = response.get(item_key, {}).get(api.items_key)
        if tracks and extend_features:
            await api.extend_tracks(tracks, limit=response[item_key]["limit"], features=True)

        return not extend_tracks

    async def reload(
            self, extend_artists: bool = False, extend_tracks: bool = False, extend_features: bool = False, *_, **__
    ) -> None:
        self._check_for_api()
        response = next(iter(await self.api.get_items(self.url, kind=RemoteObjectType.ALBUM, extend=False)))

        skip_checks = await self._extend_response(
            response=response,
            api=self.api,
            extend_tracks=extend_tracks,
            extend_artists=extend_artists,
            extend_features=extend_features,
        )

        self.__init__(response=response, api=self.api, skip_checks=skip_checks)


class SpotifyArtist(RemoteArtist[SpotifyAlbum], SpotifyCollectionLoader[SpotifyAlbum]):
    """Extracts key ``artist`` data from a Spotify API JSON response."""

    __slots__ = ("_albums",)

    @staticmethod
    def _validate_item_type(items: Any | Iterable[Any]) -> bool:
        if isinstance(items, Iterable):
            return all(isinstance(item, SpotifyAlbum) for item in items)
        return isinstance(items, SpotifyAlbum)

    @property
    def name(self):
        return self.artist

    @property
    def items(self) -> list[SpotifyAlbum]:
        """The albums this artist is featured on"""
        return self._albums

    @property
    def artist(self):
        return self.response["name"]

    @property
    def albums(self) -> list[SpotifyAlbum]:
        album_frequencies = [
            (album, sum(artist.name == self.name for track in album for artist in track.artists))
            for album in self._albums
        ]
        return [album for album, _ in sorted(album_frequencies, key=lambda x: x[1])]

    @property
    def genres(self):
        return self.response.get("genres")

    @property
    def image_links(self):
        if not (images := self.response.get("images")):
            return {}

        images = {image["height"]: image["url"] for image in images}
        return {"cover_front": url for height, url in images.items() if height == max(images)}

    @property
    def rating(self):
        rating = self.response.get("popularity")
        return int(rating) if rating is not None else None

    @property
    def followers(self) -> int | None:
        """The total number of followers for this artist"""
        followers = self.response.get("followers", {}).get("total")
        return int(followers) if followers else None

    def __init__(self, response: dict[str, Any], api: SpotifyAPI | None = None, skip_checks: bool = False):
        self._albums: list[SpotifyAlbum] | None = None
        super().__init__(response=response, api=api, skip_checks=skip_checks)

    def refresh(self, skip_checks: bool = False) -> None:
        self._albums = [
            SpotifyAlbum(album, api=self.api, skip_checks=skip_checks)
            for album in self.response.get("albums", {}).get("items", [])
        ]

    @classmethod
    def _get_item_kind(cls, api: SpotifyAPI) -> RemoteObjectType:
        return RemoteObjectType.ALBUM

    @classmethod
    async def _get_items(
            cls, items: Collection[str] | MutableMapping[str, Any], api: SpotifyAPI
    ) -> list[dict[str, Any]]:
        return await api.get_items(items, extend=False)

    @classmethod
    def _filter_items(cls, items: Iterable[SpotifyAlbum], response: dict[str, Any]) -> Iterable[SpotifyAlbum]:
        """Filter down and return only ``items`` the items associated with the given ``response``"""
        return [
            item for item in items
            if any(artist["id"] == response["id"] for artist in item.response.get("artists", []))
        ]

    @classmethod
    async def _extend_response(
            cls,
            response: MutableMapping[str, Any],
            api: SpotifyAPI,
            leave_bar: bool = True,
            extend_albums: bool = False,
            extend_tracks: bool = False,
            extend_features: bool = False,
            *_,
            **__
    ) -> bool:
        item_kind = RemoteObjectType.ALBUM
        item_key = item_kind.name.lower() + "s"

        response_items = response.get(item_key, {})
        has_all_albums = item_key in response and len(response_items[api.items_key]) == response_items["total"]
        if extend_albums and not has_all_albums:
            await api.get_artist_albums(response, limit=response.get(item_key, {}).get("limit", 50))

        album_item_kind = api.collection_item_map[item_kind]
        album_item_key = album_item_kind.name.lower() + "s"
        albums = response.get(item_key, {}).get(api.items_key)

        if albums and extend_tracks:
            for album in albums:
                await api.extend_items(album[album_item_key], kind=item_kind, key=album_item_kind)

        if albums and extend_features:
            tracks = [track for album in albums for track in album[album_item_key]["items"]]
            await api.extend_tracks(tracks, limit=response[item_key]["limit"], features=True)

        return not extend_albums or not extend_tracks

    async def reload(
            self, extend_albums: bool = False, extend_tracks: bool = False, extend_features: bool = False, *_, **__
    ) -> None:
        self._check_for_api()
        response = await self.api.handler.get(url=self.url)

        skip_checks = await self._extend_response(
            response=response,
            api=self.api,
            extend_albums=extend_albums,
            extend_tracks=extend_tracks,
            extend_features=extend_features,
        )

        self.__init__(response=response, api=self.api, skip_checks=skip_checks)
