import re
from collections.abc import Mapping, Callable
from copy import deepcopy
from datetime import datetime
from random import choice, randrange, sample, random, shuffle
from typing import Any
from urllib.parse import unquote
from uuid import uuid4

from aioresponses import CallbackResult
from pycountry import countries, languages
from yarl import URL

from musify.libraries.remote.core.types import RemoteObjectType as ObjectType
from musify.libraries.remote.spotify.api import SpotifyAPI
from musify.libraries.remote.spotify.wrangle import SpotifyDataWrangler
from tests.libraries.remote.core.utils import RemoteMock
from tests.libraries.remote.spotify.utils import random_id
from tests.utils import random_str, random_date_str, random_dt, random_genres

# noinspection PyUnresolvedReferences
COUNTRY_CODES: tuple[str, ...] = tuple(country.alpha_2 for country in countries)
# noinspection PyUnresolvedReferences
LANGUAGE_NAMES: tuple[str, ...] = tuple(lang.name for lang in languages)
# noinspection PyUnresolvedReferences
LANGUAGE_CODES: tuple[str, ...] = tuple(lang.alpha_3.lower()[:2] + "-" + choice(COUNTRY_CODES) for lang in languages)
IMAGE_SIZES: tuple[int, ...] = tuple([64, 160, 300, 320, 500, 640, 800, 1000])


class SpotifyMock(RemoteMock):
    """Generates responses and sets up Spotify API requests mock"""

    source = SpotifyDataWrangler.source
    url_api = SpotifyDataWrangler.url_api
    url_ext = SpotifyDataWrangler.url_ext

    range_start = 25
    range_stop = 50
    range_max = 200

    limit_lower = 10
    limit_upper = 20
    limit_max = 50

    @property
    def item_type_map(self):
        return {
            ObjectType.PLAYLIST: self.playlists,
            ObjectType.ALBUM: self.albums,
            ObjectType.TRACK: self.tracks,
            ObjectType.ARTIST: self.artists,
            ObjectType.USER: self.users,
            ObjectType.SHOW: self.shows,
            ObjectType.EPISODE: self.episodes,
            ObjectType.AUDIOBOOK: self.audiobooks,
            ObjectType.CHAPTER: self.chapters,
        }

    @property
    def item_type_map_user(self):
        return {
            ObjectType.PLAYLIST: self.user_playlists,
            ObjectType.ALBUM: self.user_albums,
            ObjectType.TRACK: self.user_tracks,
            ObjectType.ARTIST: self.user_artists,
            ObjectType.SHOW: self.user_shows,
            ObjectType.EPISODE: self.user_episodes,
            ObjectType.AUDIOBOOK: self.user_audiobooks,
        }

    def calculate_pages_from_response(self, response: Mapping[str, Any], item_key: str | None = None) -> int:
        item_kind = ObjectType.from_name(response["type"])[0]
        if not item_key:
            item_key = SpotifyAPI.collection_item_map[item_kind].name.lower() + "s"

        items_block = response.get(item_key, {})
        return self.calculate_pages(limit=items_block.get("limit", 50), total=items_block.get("total", 0))

    def __init__(self, **kwargs):
        super().__init__(case_sensitive=True, **{k: v for k, v in kwargs.items() if k != "case_sensitive"})

        def get_duration(track: dict[str, Any]) -> int:
            """Get duration in ms from response"""
            if isinstance(track["duration_ms"], dict):
                return track["duration_ms"]["totalMilliseconds"]
            return track["duration_ms"]

        # generate initial responses for generic item calls
        # track count needs to be at least 10 more than total possible collection item count i.e. `range_max`
        self.tracks = [self.generate_track() for _ in range(self.range_max + 20)]
        self.audio_features = {
            t["id"]: self.generate_audio_features(track_id=t["id"], duration_ms=get_duration(t)) for t in self.tracks
        }
        self.audio_analysis = {
            t["id"]: self.generate_audio_analysis(duration_ms=get_duration(t)) for t in self.tracks
        }

        self.artists = [self.generate_artist() for _ in range(randrange(self.range_start, self.range_stop))]
        self.users = [self.generate_user() for _ in range(randrange(self.range_start, self.range_stop))]
        self.episodes = [self.generate_episode() for _ in range(self.range_max + 20)]
        self.chapters = [self.generate_chapter() for _ in range(self.range_max + 20)]

        self.playlists = [
            self.generate_playlist(owner=choice(self.users))
            for _ in range(randrange(self.range_start, self.range_stop))
        ]
        self.albums = [self.generate_album() for _ in range(randrange(self.range_start, self.range_stop))]
        self.shows = [self.generate_show() for _ in range(randrange(self.range_start, self.range_stop))]
        self.audiobooks = [self.generate_audiobook() for _ in range(randrange(self.range_start, self.range_stop))]

        self.artist_albums = []
        for album in self.albums:
            album = {
                k: v for k, v in album.items()
                if k not in {"tracks", "copyrights", "external_ids", "genres", "label", "popularity"}
            }
            album["album_group"] = choice(("album", "single", "compilation", "appears_on"))
            self.artist_albums.append(deepcopy(album))

        self.setup_specific_conditions()
        self.setup_valid_references()
        self.setup_specific_conditions_artist_albums()

        # randomly choose currently authenticated user and setup mock
        self.user = choice(self.users)
        self.user_id = self.user["id"]

        self.user_tracks = [
            self.format_user_item(deepcopy(item), ObjectType.TRACK) for item in self.tracks[:self.range_max]
        ]
        self.user_artists = deepcopy(self.artists)
        self.user_episodes = [
            self.format_user_item(deepcopy(item), ObjectType.EPISODE) for item in self.episodes[:self.range_max]
        ]

        # generate responses for saved user's item calls and id_map for reference by tests
        self.user_playlists = [
            self.generate_playlist(owner=self.user) for _ in range(randrange(self.range_start, self.range_stop))
        ]
        self.user_albums = [self.format_user_item(deepcopy(item), ObjectType.ALBUM) for item in self.albums]
        self.user_shows = [self.format_user_item(deepcopy(item), ObjectType.SHOW) for item in self.shows]
        self.user_audiobooks = [self.format_user_item(deepcopy(item), ObjectType.AUDIOBOOK) for item in self.audiobooks]

        self.setup_specific_conditions_user()

    ###########################################################################
    ## Setup - cross-reference
    ###########################################################################
    def setup_specific_conditions(self):
        """Some tests need items of certain size and properties. Set these up for non-user items here."""
        self.shows.append(self.generate_show(episode_count=100))
        self.audiobooks.append(self.generate_audiobook(chapter_count=100))
        self.playlists.append(self.generate_playlist(item_count=100))

        album = self.generate_album(track_count=100)
        album["genres"] = random_genres(5)
        self.albums.append(album)

        # ensure a certain minimum number of small albums
        count = max(10 - sum(1 for album in self.albums if 2 < album["tracks"]["total"] <= self.limit_lower), 0)
        for _ in range(count):
            self.albums.append(self.generate_album(track_count=randrange(3, self.limit_lower)))

    def setup_specific_conditions_artist_albums(self):
        """Some tests need artist albums to return results of certain size and properties. Set these up here."""
        # one artist with many albums associated for artist albums test
        artist = deepcopy(choice(self.artists))
        artist = {k: v for k, v in artist.items() if k not in {"followers", "genres", "images", "popularity"}}
        album_types = ("album", "single")
        albums = [
            album for album in self.artist_albums
            if any(art["id"] == artist["id"] for art in album["artists"]) and album["album_type"] in album_types
        ]

        for _ in range(self.range_start - len(albums)):
            album = self.generate_album()
            album["artists"].append(deepcopy(artist))
            self.albums.append(deepcopy(album))

            album = {
                k: v for k, v in album.items()
                if k not in {"tracks", "copyrights", "external_ids", "genres", "label", "popularity"}
            }
            album["album_group"] = choice(album_types)
            self.artist_albums.append(deepcopy(album))

    def setup_specific_conditions_user(self):
        """Some tests need items of certain size and properties. Set these up for user items here."""
        # ensure a certain minimum number of small user playlists
        count = max(10 - sum(1 for pl in self.user_playlists if self.limit_lower < pl["tracks"]["total"] <= 60), 0)
        for _ in range(count):
            pl = self.generate_playlist(owner=self.user, item_count=randrange(self.limit_lower + 1, 60))
            self.user_playlists.append(pl)

    def setup_valid_references(self):
        """Sets up cross-referenced valid responses needed for RemoteObject tests"""
        # ensure album artists and tracks relate to actual callable items
        for album in self.albums:
            artists = deepcopy(sample(self.artists, k=len(album["artists"])))
            for artist in artists:
                for key in {"followers", "genres", "images", "popularity"}:
                    artist.pop(key, None)
            album["artists"] = artists

            # ensure that the currently collected tracks have
            for track in album["tracks"]["items"]:
                track.pop("album", None)
                track["artists"] = deepcopy(artists)

        # ensure that track albums and artists relate to actual callable items
        artist_ids = {artist["id"] for artist in self.artists}
        album_ids = {album["id"] for album in self.albums}
        for track in self.tracks:
            if track["album"]["id"] not in album_ids:
                track["album"] = {
                    k: v for k, v in deepcopy(choice(self.albums)).items()
                    if k not in {"tracks", "copyrights", "external_ids", "genres", "label", "popularity"}
                }
            for artist in track["artists"]:
                if artist["id"] not in artist_ids:
                    artist.clear()
                    artist |= {
                        k: v for k, v in choice(self.artists).items()
                        if k not in {"followers", "genres", "images", "popularity"}
                    }

    ###########################################################################
    ## Setup - requests
    ###########################################################################
    def setup_mock(self):
        url_api = self.url_api

        self.setup_search_mock()
        self.get(
            url=f"{url_api}/me",
            callback=lambda *_, **__: CallbackResult(method="GET", payload=deepcopy(self.user)),
            repeat=True
        )

        # setup responses as needed for each item type
        self.setup_items_mock(kind=ObjectType.TRACK, id_map={item["id"]: item for item in self.tracks})
        self.setup_items_mock(kind="audio-features", id_map=self.audio_features)
        self.setup_items_mock(kind="audio-analysis", id_map=self.audio_analysis, batchable=False)

        self.setup_items_mock(kind=ObjectType.ARTIST, id_map={item["id"]: item for item in self.artists})
        users_map = {item["id"]: item for item in self.users}
        self.setup_items_mock(kind=ObjectType.USER, id_map=users_map, batchable=False)
        self.setup_items_mock(kind=ObjectType.EPISODE, id_map={item["id"]: item for item in self.episodes})
        self.setup_items_mock(kind=ObjectType.CHAPTER, id_map={item["id"]: item for item in self.chapters})

        # setup responses as needed for each collection type with following config:
        # (RemoteObjectType, initial API responses to set up, item generator, item key, batchable)
        config: tuple[tuple[
            ObjectType, list[dict[str, Any]], Callable[[dict[str, Any], int], list[dict[str, Any]]], str, bool
        ], ...] = (
            (ObjectType.PLAYLIST, self.playlists + self.user_playlists, self.generate_playlist_tracks, "tracks", False),
            (ObjectType.ALBUM, self.albums, self.generate_album_tracks, "tracks", True),
            (ObjectType.SHOW, self.shows, self.generate_show_episodes, "episodes", True),
            (ObjectType.AUDIOBOOK, self.audiobooks, self.generate_audiobook_chapters, "chapters", True),
        )

        for kind, source, generator, key, batchable in config:
            source_map = {item["id"]: item for item in source}
            self.setup_items_mock(kind=kind, id_map=source_map, batchable=batchable)
            for id_, collection in source_map.items():
                count = collection[key]["total"] - len(collection[key]["items"])
                items = collection[key]["items"].copy()
                items += generator(collection, count)

                url = f"{collection["href"]}/{key}"
                self.setup_items_block_mock(url_items=url, items=items, total=collection[key]["total"])

        # artist's albums
        for i, artist in enumerate(self.artists):
            id_ = artist["id"]
            items = [album for album in self.artist_albums if any(art["id"] == id_ for art in album["artists"])]
            url = f"{url_api}/artists/{id_}/albums"
            self.setup_items_block_mock(url_items=url, items=items)

        # when getting a user's playlists, individual tracks are not returned
        user_playlists_reduced = deepcopy(self.user_playlists)
        for playlist in user_playlists_reduced:
            playlist["tracks"] = {"href": playlist["tracks"]["href"], "total": playlist["tracks"]["total"]}

        # setup responses as needed for each 'user's saved' type
        self.setup_items_block_mock(url_items=f"{url_api}/me/tracks", items=self.user_tracks)
        self.setup_items_block_mock(url_items=f"{url_api}/me/following", items=self.user_artists)
        self.setup_items_block_mock(url_items=f"{url_api}/me/episodes", items=self.user_episodes)

        self.setup_items_block_mock(url_items=f"{url_api}/me/playlists", items=user_playlists_reduced)
        self.setup_items_block_mock(url_items=f"{url_api}/users/{self.user_id}/playlists", items=user_playlists_reduced)
        self.setup_items_block_mock(url_items=f"{url_api}/me/albums", items=self.user_albums)
        self.setup_items_block_mock(url_items=f"{url_api}/me/shows", items=self.user_shows)
        self.setup_items_block_mock(url_items=f"{url_api}/me/audiobooks", items=self.user_audiobooks)

        self.setup_playlist_operations_mock()

    def setup_search_mock(self):
        """Setup requests mock for getting responses from the ``/search`` endpoint"""
        def callback(url: URL, params: dict[str, Any], **_) -> CallbackResult:
            """Dynamically generate expected batched response from a request with an 'ids' param"""
            params = params if params is not None else {}
            params |= url.query

            limit = int(params["limit"])
            offset = int(params.get("offset", 0))
            query = unquote(params["q"])
            kinds = unquote(params["type"]).split(",")

            count = 0
            total = 0
            results = {}
            for kind in kinds:
                kind_enum = ObjectType.from_name(kind)[0]
                values = self.item_type_map[kind_enum]
                # simple match on name for given query
                results[kind + "s"] = [v for v in values if v["name"].casefold() == query.casefold()]
                total += len(values)

                # ensure minimal items response for collections to improve speed on some tests
                if kind_enum in SpotifyAPI.collection_item_map:
                    key = SpotifyAPI.collection_item_map[kind_enum].name.lower() + "s"
                    values = [v for v in values if 2 < v[key]["total"] <= self.limit_lower]

                available = len(values) - len(results[kind + "s"])
                if len(results[kind + "s"]) < limit and available:
                    offset_max = min(available, offset + limit) - len(results[kind + "s"]) - count
                    results[kind + "s"] += values[offset:max(offset, offset_max)]

                shuffle(results[kind + "s"])
                count += len(results[kind + "s"])

            payload = {
                kind: self.format_items_block(url=str(url), items=items, offset=offset, limit=limit, total=total)
                for kind, items in results.items()
            }
            return CallbackResult(method="GET", payload=payload)

        url_search = f"{self.url_api}/search"
        self.get(url=re.compile(url_search + r"\?"), callback=callback, repeat=True)

    def setup_items_mock(
            self, kind: ObjectType | str, id_map: dict[str, dict[str, Any]], batchable: bool = True
    ) -> None:
        """
        Setup requests mock for getting responses from the given ``id_map``.
        Sets up mocks for /{``kind``}/{ID} endpoints for multi-calls and,
        when ``batchable`` is True, /{``kind``}?... for batchable-calls.
        """
        def callback(url: URL, params: dict[str, Any] = None, **_) -> CallbackResult:
            """Dynamically generate expected batched response from a request with an 'ids' param"""
            params = params if params is not None else {}
            params |= url.query
            req_kind = url.path.split("/")[-1].replace("-", "_")

            id_list = unquote(params["ids"]).split(",")
            payload = {req_kind: [deepcopy(id_map[i]) for i in id_list]}
            return CallbackResult(method="GET", payload=payload)

        url_api = self.url_api
        url_items = f"{url_api}/{kind.name.lower()}s" if isinstance(kind, ObjectType) else f"{url_api}/{kind}"

        if batchable:  # item batched calls
            self.get(url=re.compile(url_items + r"\?"), callback=callback, repeat=True)
        for id_, item in id_map.items():  # item multi calls
            self.get(url=re.compile(f"{url_items}/{id_}" + r"(\?|$)"), payload=deepcopy(item), repeat=True)

    def setup_items_block_mock(self, url_items: str, items: list[dict[str, Any]], total: int | None = None) -> None:
        """Setup requests mock for returning preset responses from the given ``items`` in an 'items block' format."""
        def callback(url: URL, params: dict[str, Any] = None, **__) -> CallbackResult:
            """Dynamically generate expected response for an items block from the given ``generator``"""
            params = params if params is not None else {}
            params |= url.query
            limit = int(params["limit"])
            offset = int(params.get("offset", 0))

            available = items
            available_total = total
            if re.match(r".*/artists/\w+/albums$", url.path) and "include_groups" in params:
                # special case for artist's albums
                types = unquote(params["include_groups"]).split(",")
                available = [i for i in items if i["album_type"] in types]
                available_total = len(available)

            it = deepcopy(available[offset: offset + limit])
            items_block = self.format_items_block(
                url=str(url), items=it, offset=offset, limit=limit, total=available_total
            )

            if url.path.endswith("me/following"):  # special case for following artists
                items_block["cursors"] = {}
                if offset < available_total:
                    items_block["cursors"]["after"] = it[-1]["id"]
                if (offset - limit) > 0:
                    items_block["cursors"]["before"] = items[offset - limit]["id"]

                items_block = {"artists": items_block}

            return CallbackResult(method="GET", payload=items_block)

        total = total or len(items)
        self.get(url=re.compile(url_items + r"\?"), callback=callback, repeat=True)

    def setup_playlist_operations_mock(self) -> None:
        """Generate playlist and setup ``requests_mock`` for playlist operations tests"""
        for playlist in self.user_playlists:
            self.post(
                url=re.compile(playlist["href"] + "/tracks"), payload={"snapshot_id": str(uuid4())}, repeat=True
            )
            self.put(url=re.compile(playlist["href"] + "/followers"), repeat=True)
            self.delete(url=re.compile(playlist["href"] + "/followers"), repeat=True)
            self.delete(
                url=re.compile(playlist["href"] + "/tracks"), payload={"snapshot_id": str(uuid4())}, repeat=True
            )

        def callback(_: str, json: dict[str, Any], **__) -> CallbackResult:
            """Process body and generate playlist response data"""
            playlist_ids = {pl["id"] for pl in self.playlists}
            payload = self.generate_playlist(owner=self.user, item_count=0)
            while payload["id"] in playlist_ids:
                payload = self.generate_playlist(owner=self.user, item_count=0)

            payload["name"] = json["name"]
            payload["description"] = json["description"]
            payload["public"] = json["public"]
            payload["collaborative"] = json["collaborative"]
            payload["owner"] = self.user_playlists[0]["owner"]

            self.get(url=re.compile(payload["href"]), payload=payload, repeat=True)
            self.post(url=re.compile(payload["href"] + "/tracks"), payload={"snapshot_id": str(uuid4())}, repeat=True)
            self.put(url=re.compile(payload["href"] + "/followers"), repeat=True)
            self.delete(url=re.compile(payload["href"] + "/followers"), repeat=True)
            self.delete(url=re.compile(payload["href"] + "/tracks"), payload={"snapshot_id": str(uuid4())}, repeat=True)

            # for some reason, spotify returns initial response for created playlists with different owner IDs
            payload = deepcopy(payload)
            payload["owner"] = self.generate_owner()

            return CallbackResult(method="POST", payload=payload)

        # add new request matches when creating new playlists
        url = f"{self.url_api}/users/{self.user_id}/playlists"
        self.post(url=url, callback=callback, repeat=True)

    ###########################################################################
    ## Formatters
    ###########################################################################
    def format_items_block(
            self, url: str, items: list[dict[str, Any]], offset: int = 0, limit: int = 20, total: int = limit_max
    ) -> dict[str, Any]:
        """Format an items block response from a list of items and a URL base."""
        href = SpotifyAPI.format_next_url(url=url, offset=offset, limit=limit)
        limit = min(max(limit, 1), self.limit_max)  # limit must be between 1 and 50

        prev_offset = offset - limit
        prev_url = SpotifyAPI.format_next_url(url=url, offset=prev_offset, limit=limit) if prev_offset >= 0 else None
        next_offset = offset + limit
        next_url = SpotifyAPI.format_next_url(url=url, offset=next_offset, limit=limit) if next_offset < total else None

        return {
            "href": href,
            "limit": limit,
            "next": next_url,
            "offset": offset,
            "previous": prev_url,
            "total": total,
            "items": items
        }

    @staticmethod
    def format_user_item(response: dict[str, Any], kind: ObjectType) -> dict[str, Any]:
        """Format a response to expected response for a 'saved user's...' endpoint type"""
        return {
            "added_at": random_dt(start=datetime(2008, 10, 7)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            kind.name.lower(): response
        }

    ###########################################################################
    ## Generators - helpers
    ###########################################################################
    def _get_count(self, response: Mapping[str, Any], key: str, total: int) -> int:
        """
        Generate a value for the number of items to generate from the 'limit' key in the ``key`` of the ``response``
        or use the 'total' value minus the current number of items.
        When ``key`` cannot be found, assume 0 current items present, and a limit of 50.
        Will sometimes produce a count that will force pagination

        :param response: The response to generate items for.
        :param key: The key under which optional 'limit' and 'items' keys can be found.
        :param total: The total number of items in this response.
        :return: The count produced.
        """
        current = len(response.get(key, {}).get("items", []))

        # force pagination testing when range > 1
        remaining = total - current
        limit = max(min(response.get(key, {}).get("limit", remaining // randrange(1, 4)), self.limit_max), 1)
        count = limit if limit < remaining else remaining

        if current + count > total:
            raise Exception(
                f"Invalid count, will generate too many items | current={current} | count={count} | total={total}"
            )

        return count

    @staticmethod
    def generate_external_ids() -> dict[str, Any]:
        """Return a randomly generated set of external IDs."""
        external_ids = {}

        if choice([True, False]):
            registrant = random_str(3, 3)
            year = str(random_dt().year)[:-2]
            designation = str(randrange(int(10e5), int(10e6 - 1)))
            external_ids["isrc"] = f"{choice(COUNTRY_CODES)}{registrant}{year}{designation}".upper()
        if choice([True, False]):
            external_ids["ran"] = str(randrange(int(10e13), int(10e14 - 1)))
        if choice([True, False]):
            external_ids["upc"] = str(randrange(int(10e12), int(10e13 - 1)))
        return external_ids

    @staticmethod
    def generate_images() -> list[dict[str, Any]]:
        """Return a list of randomly generated Spotify API responses for an image."""
        def generate_image(size: int = choice(IMAGE_SIZES)):
            """Return a randomly generated Spotify API response for an image."""
            return {"url": f"https://i.scdn.co/image/{random_str(40, 40)}", "height": size, "width": size}

        images = [generate_image(size) for size in sample(IMAGE_SIZES, k=randrange(0, len(IMAGE_SIZES)))]
        images.sort(key=lambda x: x["height"], reverse=True)
        return images

    ###########################################################################
    ## Generators - TRACK
    ###########################################################################
    def generate_track(self, album: bool = True, artists: bool = True, features: bool = False) -> dict[str, Any]:
        """
        Return a randomly generated Spotify API response for a Track.

        :param album: Add randomly generated album information to the response as per documentation.
        :param artists: Add randomly generated artists information to the response as per documentation.
        :param features: Add randomly generated audio features information to the response as per documentation.
        """
        kind = ObjectType.TRACK.name.lower()
        track_id = random_id()
        duration_ms = randrange(int(10e4), int(6*10e5))  # 1 second to 10 minutes range

        response = {
            "available_markets": sample(COUNTRY_CODES, k=randrange(1, 5)),
            "disc_number": randrange(1, 4),
            "duration_ms": choice((duration_ms, {"totalMilliseconds": duration_ms})),
            "explicit": choice([True, False, None]),
            "external_ids": self.generate_external_ids(),
            "external_urls": {self.source.lower(): f"{self.url_ext}/{kind}/{track_id}"},
            "href": f"{self.url_api}/{kind}s/{track_id}",
            "id": track_id,
            "name": random_str(30, 50),
            "popularity": randrange(0, 100),
            "preview_url": None,
            "track_number": randrange(1, 30),
            "type": kind,
            "uri": f"{self.source.lower()}:{kind}:{track_id}",
            "is_local": False
        }

        if artists:
            response["artists"] = [self.generate_artist(properties=False) for _ in range(randrange(1, 4))]

        if album:
            response["album"] = self.generate_album(tracks=False, properties=False, artists=not artists)
            if artists:
                response["album"]["artists"] = deepcopy(response["artists"])

        if features:
            audio_features = self.generate_audio_features(track_id=track_id, duration_ms=response["duration_ms"])
            response["audio_features"] = audio_features

        return response

    def generate_audio_features(self, track_id: str | None = None, duration_ms: int | None = None) -> dict[str, Any]:
        """
        Return a randomly generated Spotify API response for a Track's audio features.

        :param track_id: The Track ID to use in the response. Will randomly generate if not given.
        :param duration_ms: The duration of the track in ms to use in the response. Will randomly generate if not given.
        """
        kind = ObjectType.TRACK.name.lower()
        track_id = track_id or random_id()
        duration_ms = duration_ms or randrange(int(10e4), int(6*10e5))  # 1 second to 10 minutes range

        # noinspection SpellCheckingInspection
        return {
            "acousticness": random(),
            "analysis_url": f"{self.url_api}/audio-analysis/{track_id}",
            "danceability": random(),
            "duration_ms": duration_ms,
            "energy": random(),
            "id": track_id,
            "instrumentalness": random(),
            "key": randrange(-1, 11),
            "liveness": random(),
            "loudness": -random() * 60,
            "mode": choice([0, 1]),
            "speechiness": random(),
            "tempo": random() * 100 + 50,
            "time_signature": randrange(3, 7),
            "track_href": f"{self.url_api}/{kind}s/{track_id}",
            "type": "audio_features",
            "uri": f"{self.source.lower()}:{kind}:{track_id}",
            "valence": random()
        }

    @staticmethod
    def generate_audio_analysis(duration_ms: int | None = None) -> dict[str, Any]:
        """
        Return a randomly generated Spotify API response for a Track's audio features.

        :param duration_ms: The duration of the track in ms to use in the response. Will randomly generate if not given.
        """
        duration_ms = duration_ms or randrange(int(10e4), int(6*10e5))  # 1 second to 10 minutes range
        return {"track": {"duration": duration_ms / 1000}}

    ###########################################################################
    ## Generators - ARTIST
    ###########################################################################
    def generate_artist(self, properties: bool = True) -> dict[str, Any]:
        """
        Return a randomly generated Spotify API response for an Artist.

        :param properties: Add extra randomly generated information to the response as per documentation.
        """
        kind = ObjectType.ARTIST.name.lower()
        artist_id = random_id()

        response = {
            "external_urls": {self.source.lower(): f"{self.url_ext}/{kind}/{artist_id}"},
            "href": f"{self.url_api}/{kind}s/{artist_id}",
            "id": artist_id,
            "name": random_str(5, 30),
            "type": kind,
            "uri": f"{self.source.lower()}:{kind}:{artist_id}"
        }

        return self.extend_artist(response=response, properties=properties)

    def extend_artist(self, response: dict[str, Any], properties: bool = True) -> dict[str, Any]:
        """
        Extend a given randomly generated Spotify API ``response`` for an Artist.

        :param response: The response to extend.
        :param properties: Add extra randomly generated information to the response as per documentation.
        """
        if properties:
            response |= {
                "followers": {"href": None, "total": randrange(0, int(8e10))},
                "genres": random_genres(),
                "images": self.generate_images(),
                "popularity": randrange(0, 100)
            }
        return response

    ###########################################################################
    ## Generators - USER
    ###########################################################################
    def generate_user(self) -> dict[str, Any]:
        """Return a randomly generated Spotify API response for a User."""
        kind = ObjectType.USER.name.lower()
        user_id = random_str(30, 50)

        response = {
            "country": choice(COUNTRY_CODES),
            "display_name": random_str(5, 30),
            "email": random_str(15, 50),
            "explicit_content": {
                "filter_enabled": choice([True, False]),
                "filter_locked": choice([True, False])
            },
            "external_urls": {self.source.lower(): f"{self.url_ext}/{kind}/{user_id}"},
            "followers": {"href": None, "total": randrange(0, int(8e10))},
            "href": f"{self.url_api}/{kind}s/{user_id}",
            "id": user_id,
            "images": self.generate_images(),
            "product": choice(["premium", "free", "open"]),
            "type": kind,
            "uri": f"{self.source.lower()}:{kind}:{user_id}"
        }

        return response

    def generate_owner(
            self, user: Mapping[str, Any] | None = None, user_id: str | None = None, user_name: str | None = None
    ) -> dict[str, Any]:
        """Return a randomly generated Spotify API response for an owner"""
        kind = ObjectType.USER.name.lower()
        user_id = user_id or str(uuid4())
        user_name = user_name or random_str(5, 30)
        ext_urls = user["external_urls"] if user else {
            self.source.lower(): f"{self.url_ext}/{kind}/{user_id}"
        }

        return {
            "display_name": user["display_name"] if user else user_name,
            "external_urls": ext_urls,
            "href": user["href"] if user else f"{self.url_api}/{kind}s/{user_id}",
            "id": user["id"] if user else user_id,
            "type": user["type"] if user else kind,
            "uri": user["uri"] if user else f"{self.source.lower()}:{kind}:{user_id}",
        }

    def generate_owner_from_api(self, api: SpotifyAPI | None = None) -> dict[str, Any]:
        """Return an owner block from the properties of the given :py:class:`SpotifyAPI` object"""
        return self.generate_owner(user_id=api.user_id, user_name=api.user_name)

    ###########################################################################
    ## Generators - PLAYLIST
    ###########################################################################
    def generate_playlist(
            self,
            item_count: int | None = None,
            owner: str | dict[str, Any] | None = None,
            api: SpotifyAPI | None = None,
            use_stored: bool = True,
    ) -> dict[str, Any]:
        """
        Return a randomly generated Spotify API response for a Playlist.

        :param item_count: The total number of items this playlist should have.
        :param owner: Provide an optional ``owner`` block representing a user who owns the playlist,
            or a user_id string to use when generating an owner block for the playlist.
            Has priority over ``api`` when ``owner`` is an ``owner`` block.
        :param api: An optional, authenticated :py:class:`SpotifyAPI` object to extract user information from.
            This will be used to generate an owner block to playlist when ``owner`` is None.
            Has priority over ``owner`` when ``owner`` is a string.
        :param use_stored: When True, add stored items to the playlist response instead of generating new ones.
        """
        kind = ObjectType.PLAYLIST.name.lower()
        playlist_id = random_id()
        url = f"{self.url_api}/{kind}s/{playlist_id}"

        item_count = item_count if item_count is not None else randrange(0, self.range_max)
        public = choice([True, False])

        if isinstance(owner, dict):
            owner = self.generate_owner(user=owner)
        elif api:
            owner = self.generate_owner_from_api(api=api)
        else:
            owner = self.generate_owner(user_id=owner)

        response = {
            "collaborative": choice([True, False]) if not public else False,
            "description": random_str(20, 100),
            "external_urls": {
                self.source.lower(): f"{self.url_ext}/{kind}/{playlist_id}"
            },
            "followers": {"href": None, "total": randrange(0, int(8e10))},
            "href": url,
            "id": playlist_id,
            "images": self.generate_images(),
            "name": random_str(30, 50),
            "owner": owner,
            "primary_color": None,
            "public": public,
            "snapshot_id": random_str(60, 60),
            "tracks": {"href": f"{url}/tracks", "total": item_count},
            "type": kind,
            "uri": f"{self.source.lower()}:{kind}:{playlist_id}",
        }

        tracks = self.generate_playlist_tracks(response=response, use_stored=use_stored)
        url = response["tracks"]["href"]
        response["tracks"] = self.format_items_block(url=url, items=tracks, limit=len(tracks), total=item_count)

        return response

    def generate_playlist_tracks(
            self, response: dict[str, Any], count: int = 0, use_stored: bool = True
    ) -> list[dict[str, Any]]:
        """
        Randomly generate playlist tracks for a given randomly generated Spotify API Playlist ``response``.

        :param response: The Playlist response.
        :param count: The number of tracks to generate.
            If 0, attempt to get this number from the 'limit' key in the 'tracks' key of the response
            or use the 'total' value minus the current number of tracks.
        :param use_stored: When True, use the stored tracks instead of generating new ones.
        :return: A list of the randomly generated tracks.
        """
        total = response["tracks"]["total"]
        if not count:
            count = self._get_count(response=response, key="tracks", total=total)

        owner = deepcopy(response["owner"])
        owner.pop("display_name", None)

        if use_stored and self.tracks:
            # ensure only unique items added; unique collections are needed for certain tests
            taken = {item["track"]["uri"] for item in response.get("tracks", {}).get("items", [])}
            available = [item for item in self.tracks[:self.range_max] if item["uri"] not in taken]
            items = deepcopy(sample(available, k=count))
        else:
            items = [self.generate_track(album=False, artists=False) for _ in range(count)]

        for item in items:
            item_copy = deepcopy(item) | {"episode": False, "track": True}
            item.clear()
            item |= self.format_user_item(response=item_copy, kind=ObjectType.TRACK)
            item |= {"added_by": choice((owner, self.generate_owner())), "is_local": item["track"]["is_local"]}

        return items

    ###########################################################################
    ## Generators - ALBUM
    ###########################################################################
    def generate_album(
            self,
            track_count: int | None = None,
            tracks: bool = True,
            artists: bool = True,
            properties: bool = True,
            use_stored: bool = True,
    ) -> dict[str, Any]:
        """
        Return a randomly generated Spotify API response for an Album.

        :param track_count: The total number of tracks this album should have.
        :param tracks: Add randomly generated tracks information to the response as per documentation.
        :param artists: Add randomly generated artists information to the response as per documentation.
        :param properties: Add extra randomly generated properties information to the response as per documentation.
        :param use_stored: When True, add stored tracks to the playlist response instead of generating new ones.
        """
        kind = ObjectType.ALBUM.name.lower()
        album_id = random_id()
        track_count = track_count if track_count is not None else randrange(1, self.range_max // 4)

        response = {
            "album_type": choice((kind, "single", "compilation")),
            "total_tracks": track_count,
            "available_markets": sample(COUNTRY_CODES, k=randrange(1, 5)),
            "external_urls": {self.source.lower(): f"{self.url_ext}/{kind}/{album_id}"},
            "href": f"{self.url_api}/{kind}s/{album_id}",
            "id": album_id,
            "images": self.generate_images(),
            "name": random_str(30, 50),
            "release_date": random_date_str(),
            "release_date_precision": choice(("day", "month", "year")),
            "type": kind,
            "uri": f"{self.source.lower()}:{kind}:{album_id}",
        }

        if tracks:
            tracks = self.generate_album_tracks(response=response, use_stored=use_stored)
            url = response["href"] + "/tracks"
            response["tracks"] = self.format_items_block(url=url, items=tracks, limit=len(tracks), total=track_count)

        if artists:
            response["artists"] = [self.generate_artist(properties=False) for _ in range(randrange(1, 4))]

        if properties:
            response |= {
                "copyrights": [
                    {"text": random_str(50, 100), "type": i} for i in ["C", "P"][:randrange(1, 2)]
                ],
                "external_ids": self.generate_external_ids(),
                "genres": random_genres(),
                "label": random_str(50, 100),
                "popularity": randrange(0, 100)
            }
        return response

    def generate_album_tracks(
            self, response: dict[str, Any], count: int = 0, use_stored: bool = True
    ) -> list[dict[str, Any]]:
        """
        Randomly generate album tracks for a given randomly generated Spotify API Album ``response``.

        :param response: The Album response.
        :param count: The number of tracks to generate.
            If 0, attempt to get this number from the 'limit' key in the 'tracks' key of the response
            or use the 'total' value minus the current number of tracks.
        :param use_stored: When True, use the stored tracks instead of generating new ones.
        :return: A list of the randomly generated tracks.
        """
        current = len(response.get("tracks", {}).get("items", []))
        total = response["total_tracks"]
        if not count:
            count = self._get_count(response=response, key="tracks", total=total)

        if response.get("artists"):
            artists = deepcopy(response["artists"])
        else:
            artists = [self.generate_artist(properties=False) for _ in range(randrange(1, 4))]

        if use_stored and self.tracks:
            # ensure only unique items added; unique collections are needed for certain tests
            taken = {item["uri"] for item in response.get("tracks", {}).get("items", [])}
            available = [item for item in self.tracks[:self.range_max] if item["uri"] not in taken]
            items = deepcopy(sample(available, k=count))
        else:
            items = [self.generate_track(album=False, artists=False) for _ in range(count)]

        [item.pop("popularity", None) for item in items]
        items = [item | {"artists": artists, "track_number": i} for i, item in enumerate(items, current + 1)]

        for item in items:
            item.pop("album", None)
            item["artists"] = deepcopy(artists)

        return items

    ###########################################################################
    ## Generators - SHOW + EPISODE
    ###########################################################################
    def generate_show(self, episode_count: int | None = None, episodes: bool = True) -> dict[str, Any]:
        """
        Return a randomly generated Spotify API response for a Show.

        :param episode_count: The total number of episodes this show should have.
        :param episodes: Add randomly generated episode information to the response as per documentation.
        """
        kind = ObjectType.SHOW.name.lower()
        show_id = random_id()
        episode_count = episode_count if episode_count is not None else randrange(1, self.range_max)

        response = {
            "available_markets": sample(COUNTRY_CODES, k=randrange(1, 5)),
            "copyrights": [
                {"text": random_str(50, 100), "type": i} for i in ["C", "P"][:randrange(1, 2)]
            ],
            "description": random_str(200, 500),
            "html_description": random_str(100, 200),
            "explicit": choice([True, False, None]),
            "external_urls": {self.source.lower(): f"{self.url_ext}/{kind}/{show_id}"},
            "href": f"{self.url_api}/{kind}s/{show_id}",
            "id": show_id,
            "images": self.generate_images(),
            "is_externally_hosted": choice([True, False, None]),
            "languages": sample(LANGUAGE_CODES, k=randrange(1, 5)),
            "media_type": random_str(10, 20),
            "name": random_str(30, 50),
            "publisher": random_str(10, 30),
            "type": "show",
            "uri": f"{self.source.lower()}:{kind}:{show_id}",
            "total_episodes": episode_count,
        }

        if episodes:
            episodes = self.generate_show_episodes(response=response)
            url = response["href"] + "/episodes"
            episodes = self.format_items_block(url=url, items=episodes, limit=len(episodes), total=episode_count)
            response["episodes"] = episodes

        return response

    def generate_episode(self, show: dict[str, Any] | bool = False) -> dict[str, Any]:
        """
        Return a randomly generated Spotify API response for an Episode.

        :param show: When value is a dict representing an API response for a show,
            add this show to the episode's response.
            When True, generate a new show response and add this to the generated episode response.
            When False, show data will not be added to the generated episode response.
        """
        kind = ObjectType.EPISODE.name.lower()
        episode_id = random_id()
        duration_ms = randrange(int(10e4), int(3.6*10e6))  # 1 second to 1 hour range

        response = {
            "audio_preview_url": f"https://podz-content.spotifycdn.com/audio/clips/{episode_id}/{uuid4()}.mp3",
            "description": random_str(200, 500),
            "html_description": random_str(100, 200),
            "duration_ms": duration_ms,
            "explicit": choice([True, False, None]),
            "external_urls": {self.source.lower(): f"{self.url_ext}/{kind}/{episode_id}"},
            "href": f"{self.url_api}/{kind}s/{episode_id}",
            "id": episode_id,
            "images": self.generate_images(),
            "is_externally_hosted": choice([True, False]),
            "is_playable": choice([True, False]),
            "language": choice(LANGUAGE_CODES),
            "languages": sample(LANGUAGE_CODES, k=randrange(1, 5)),
            "name": random_str(30, 50),
            "release_date": random_date_str(start=datetime(2008, 10, 7)),
            "release_date_precision": choice(("day", "month", "year")),
            "resume_point": {
                "fully_played": choice([True, False]),
                "resume_position_ms": randrange(0, duration_ms),
            },
            "type": "episode",
            "uri": f"{self.source.lower()}:{kind}:{episode_id}",
        }

        if isinstance(show, dict):
            show.pop("episodes", None)
            response["show"] = show
        elif show:
            response["show"] = self.generate_show(episodes=False)

        if response.get("show"):
            response["languages"] = response["show"]["languages"]

        return response

    def generate_show_episodes(
            self, response: dict[str, Any], count: int = 0, use_stored: bool = True
    ) -> list[dict[str, Any]]:
        """
        Randomly generate show episodes for a given randomly generated Spotify API Show ``response``.

        :param response: The Show response.
        :param count: The number of episodes to generate.
            If 0, attempt to get this number from the 'limit' key in the 'tracks' key of the response
            or use the 'total' value minus the current number of episodes.
        :param use_stored: When True, use the stored episodes instead of generating new ones.
        :return: A list of the episodes.
        """
        total = response["total_episodes"]
        if not count:
            count = self._get_count(response=response, key="episodes", total=total)

        if use_stored and self.episodes:
            # ensure only unique items added; unique collections are needed for certain tests
            taken = {item["uri"] for item in response.get("episodes", {}).get("items", [])}
            available = [item for item in self.episodes[:self.range_max] if item["uri"] not in taken]
            items = deepcopy(sample(available, k=count))
        else:
            items = [self.generate_episode(show=False) for _ in range(count)]

        show_reduced = {k: v for k, v in response.items() if k != "episodes"}
        for item in items:
            item["show"] = show_reduced

        return items

    ###########################################################################
    ## Generators - AUDIOBOOK + CHAPTERS
    ###########################################################################
    def generate_audiobook(self, chapter_count: int | None = None, chapters: bool = True) -> dict[str, Any]:
        """
        Return a randomly generated Spotify API response for an Audiobook.

        :param chapter_count: The total number of chapters this audiobook should have.
        :param chapters: Add randomly generated chapter information to the response as per documentation.
        """
        kind = ObjectType.AUDIOBOOK.name.lower()
        audiobook_id = random_id()
        chapter_count = chapter_count if chapter_count is not None else randrange(1, self.range_max // 4)

        response = {
            "authors": [{"name": random_str(30, 50)} for _ in range(randrange(1, 5))],
            "available_markets": sample(COUNTRY_CODES, k=randrange(1, 5)),
            "copyrights": [
                {"text": random_str(50, 100), "type": i} for i in ["C", "P"][:randrange(1, 2)]
            ],
            "description": random_str(200, 500),
            "html_description": random_str(100, 200),
            "edition": random_str(5, 20),
            "explicit": choice([True, False, None]),
            "external_urls": {
                self.source.lower(): f"{self.url_ext}/{kind}/{audiobook_id}"
            },
            "href": f"{self.url_api}/{kind}s/{audiobook_id}",
            "id": audiobook_id,
            "images": self.generate_images(),
            "languages": sample(LANGUAGE_NAMES, k=randrange(1, 5)),
            "media_type": random_str(5, 20),
            "name": random_str(30, 50),
            "narrators": [{"name": random_str(30, 50)} for _ in range(randrange(1, 10))],
            "publisher": random_str(10, 30),
            "type": "audiobook",
            "uri": f"{self.source.lower()}:{kind}:{audiobook_id}",
            "total_chapters": chapter_count,
        }

        if chapters:
            chapters = self.generate_audiobook_chapters(response=response)
            url = response["href"] + "/chapters"
            chapters = self.format_items_block(url=url, items=chapters, limit=len(chapters), total=chapter_count)
            response["chapters"] = chapters

        return response

    def generate_chapter(self, audiobook: dict[str, Any] | bool = False) -> dict[str, Any]:
        """
        Return a randomly generated Spotify API response for an Episode.

        :param audiobook: When value is a dict representing an API response for an audiobook,
            add this audiobook to the chapter's response.
            When True, generate a new audiobook response and add this to the generated chapter response.
            When False, audiobook data will not be added to the generated chapter response.
        """
        kind = ObjectType.CHAPTER.name.lower()
        chapter_id = random_id()
        duration_ms = randrange(int(10e4), int(6*10e5))  # 1 second to 10 minutes range

        response = {
            "audio_preview_url": f"https://p.scdn.co/mp3-preview/{chapter_id}",
            "available_markets": sample(COUNTRY_CODES, k=randrange(1, 5)),
            "chapter_number": randrange(0, 20),
            "description": random_str(200, 500),
            "html_description": random_str(100, 200),
            "duration_ms": duration_ms,
            "explicit": choice([True, False, None]),
            "external_urls": {self.source.lower(): f"{self.url_ext}/{kind}/{chapter_id}"},
            "href": f"{self.url_api}/{kind}s/{chapter_id}",
            "id": chapter_id,
            "images": self.generate_images(),
            "is_playable": choice([True, False]),
            "languages": sample(LANGUAGE_CODES, k=randrange(1, 5)),
            "name": random_str(30, 50),
            "release_date": random_date_str(start=datetime(2008, 10, 7)),
            "release_date_precision": choice(("day", "month", "year")),
            "resume_point": {
                "fully_played": choice([True, False]),
                "resume_position_ms": randrange(0, duration_ms),
            },
            "type": "chapter",
            "uri": f"{self.source.lower()}:{kind}:{chapter_id}",
        }

        if isinstance(audiobook, dict):
            audiobook.pop("chapter", None)
            response["audiobook"] = audiobook
        elif audiobook:
            response["audiobook"] = self.generate_audiobook(chapters=False)

        if response.get("audiobook"):
            response["chapter_number"] = randrange(0, response["audiobook"]["total_chapters"])
            response["languages"] = response["audiobook"]["languages"]

        return response

    def generate_audiobook_chapters(
            self, response: dict[str, Any], count: int = 0, use_stored: bool = True
    ) -> list[dict[str, Any]]:
        """
        Randomly generate show episodes for a given randomly generated Spotify API Chapter ``response``.

        :param response: The Chapter response.
        :param count: The number of chapters to generate.
            If 0, attempt to get this number from the 'limit' key in the 'tracks' key of the response
            or use the 'total' value minus the current number of chapters.
        :param use_stored: When True, use the stored chapters instead of generating new ones.
        :return: A list of the chapters.
        """
        current = len(response.get("chapters", {}).get("items", []))
        total = response["total_chapters"]
        if not count:
            count = self._get_count(response=response, key="chapters", total=total)

        if use_stored and self.chapters:
            # ensure only unique items added; unique collections are needed for certain tests
            taken = {item["uri"] for item in response.get("chapters", {}).get("items", [])}
            available = [item for item in self.chapters[:self.range_max] if item["uri"] not in taken]
            items = deepcopy(sample(available, k=count))
        else:
            items = [self.generate_chapter(audiobook=False) for _ in range(count)]

        audiobook_reduced = {k: v for k, v in response.items() if k != "chapters"}
        for i, item in enumerate(items, current + 1):
            item["chapter_number"] = i
            item["audiobook"] = audiobook_reduced

        return items
