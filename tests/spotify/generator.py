from collections.abc import Sequence
from copy import deepcopy
from datetime import date
from typing import Any

from faker import Faker
from yarl import URL

from tests.utils import GENRES


class SpotifyPayloadGenerator:
    """Utility class for generating random Spotify API responses for testing purposes."""
    limit_lower = 10
    limit_upper = 20
    limit_max = 50
    
    def __init__(self, faker: Faker):
        self.faker = faker

    ###########################################################################
    ## User
    ###########################################################################
    def generate_user(self) -> dict[str, Any]:
        """Return a randomly generated Spotify API response for a User."""
        payload = self.generate_owner() | {
            "country": self.faker.country_code(representation="alpha-2"),
            "email": self.faker.email(),
            "explicit_content": {
                "filter_enabled": self.faker.boolean(),
                "filter_locked": self.faker.boolean()
            },
            "followers": self.generate_followers(),
            "images": self.generate_images(),
            "product": self.faker.random_element(("premium", "free", "open")),
        }

        return payload

    def generate_owner(self) -> dict[str, Any]:
        """Return a randomly generated Spotify API response for an owner of a resource."""
        kind = "user"
        user_id = self.faker.pystr(10, 40)

        payload = {
            "display_name": self.faker.name(),
            "external_urls": self.generate_external_urls(kind, user_id),
            "href": self.generate_href(kind, user_id),
            "id": user_id,
            "type": "user",
            "uri": self.generate_uri(kind, user_id),
        }

        return payload

    ################################################################################
    ## Tracks
    ################################################################################
    def generate_track(self, extend: bool = False) -> dict[str, Any]:
        """
        Return a randomly generated Spotify API response for a track.
        Optionally include extended album and artist information.
        """
        track_id = self.generate_resource_id()
        kind = "track"

        payload = {
            "available_markets": self.generate_countries(),
            "disc_number": self.faker.random_int(1, 5),
            "duration_ms": self.generate_duration(),
            "explicit": self.faker.random_element((self.faker.boolean(), None)),
            "external_ids": self.generate_external_ids(),
            "external_urls": self.generate_external_urls(kind, track_id),
            "href": self.generate_href(kind, track_id),
            "id": track_id,
            "images": self.generate_images(),
            "name": self.faker.name(),
            "popularity": self.faker.random_int(0, 100),
            "preview_url": self.faker.random_element((None, self.faker.url())),
            "track_number": self.faker.random_int(1, 50),
            "type": kind,
            "uri": self.generate_uri(kind, track_id),
            "is_local": self.faker.boolean(),
        }

        if extend:
            album = self.generate_album()
            payload |= {
                "album": album,
                "artists": album["artists"],
            }

        return payload

    def generate_tracks(
            self, album: dict[str, Any] = None, artists: list[dict[str, Any]] = None, count: int = 0
    ) -> list[dict[str, Any]]:
        """Randomly generate tracks for a given album and set of artists."""
        if count == 0:
            count = self.faker.random_int(1, 30)

        tracks = [self.generate_track(extend=False) for _ in range(count)]

        for position, track in enumerate(tracks, 1):
            if artists:
                track["artists"] = deepcopy(artists)
            if album:
                track["album"] = deepcopy(album)
            track["track_number"] = position

            track.pop("popularity", None)

        return tracks

    def generate_audio_features(self) -> dict[str, Any]:
        """Return a randomly generated Spotify API response for a Track's audio features."""
        track_id = self.generate_resource_id()
        kind = "track"
        href = URL(self.generate_href(kind, track_id))

        # noinspection SpellCheckingInspection
        return {
            "acousticness": self.faker.random_int(0, 1000) / 1000,
            "analysis_url": href.with_path("/v1/audio-analysis/" + track_id),
            "danceability": self.faker.random_int(0, 1000) / 1000,
            "duration_ms": self.faker.random_int(int(10e4), int(6 * 10e5)),  # 1 second to 10 minutes range
            "energy": self.faker.random_int(0, 1000) / 1000,
            "id": track_id,
            "instrumentalness": self.faker.random_int(0, 1000) / 1000,
            "key": self.faker.random_int(-1, 11),
            "liveness": self.faker.random_int(0, 1000) / 1000,
            "loudness": self.faker.random_int(-60, 0),
            "mode": self.faker.random_int(0, 1),
            "speechiness": self.faker.random_int(0, 1000) / 1000,
            "tempo": self.faker.random_int(0, 120) + 60,
            "time_signature": self.faker.random_int(3, 7),
            "track_href": str(href),
            "type": "audio_features",
            "uri": self.generate_uri(kind, track_id),
            "valence": self.faker.random_int(0, 100) / 100,
        }

    def generate_audio_analysis(self) -> dict[str, Any]:
        """Return a randomly generated Spotify API response for a Track's audio analysis."""
        duration_ms = self.faker.random_int(int(10e4), int(6*10e5))  # 1 second to 10 minutes range
        return {"track": {"duration": duration_ms / 1000}}

    ################################################################################
    ## Artists
    ################################################################################
    def generate_artist(self, properties: bool = False) -> dict[str, Any]:
        """
        Return a randomly generated Spotify API response for an artist.
        Optionally include additional properties.
        """
        artist_id = self.generate_resource_id()
        kind = "artist"

        payload = {
            "external_urls": self.generate_external_urls(kind, artist_id),
            "href": self.generate_href(kind, artist_id),
            "id": artist_id,
            "name": self.faker.name(),
            "type": kind,
            "uri": self.generate_uri(kind, artist_id),
        }

        if properties:
            payload |= {
                "followers": self.generate_followers(),
                "genres": self.generate_genres(),
                "images": self.generate_images(),
                "popularity": self.faker.random_int(0, 100),
            }

        return payload

    ################################################################################
    ## Album generators
    ################################################################################
    def generate_album(self, tracks: bool = False, properties: bool = False) -> dict[str, Any]:
        """
        Return a randomly generated Spotify API response for an album.
        Optionally include track payloads or additional properties.
        """
        album_id = self.generate_resource_id()
        kind = "album"
        album_href = self.generate_href("album", album_id)
        track_count = self.faker.random_int(1, 30)
        artists = [self.generate_artist() for _ in range(self.faker.random_int(1, 5))]

        payload = {
            "album_type": self.faker.random_element(("album", "single", "compilation")),
            "total_tracks": track_count,
            "available_markets": self.generate_countries(),
            "external_urls": self.generate_external_urls(kind, album_id),
            "href": album_href,
            "id": album_id,
            "images": self.generate_images(),
            "name": self.faker.name(),
            "release_date": self.faker.past_date(date(1990, 1, 1)).isoformat(),
            "release_date_precision": self.faker.random_element(("year", "month", "day")),
            "type": kind,
            "uri": self.generate_uri(kind, album_id),
            "artists": artists,
        }

        if tracks:
            tracks = self.generate_tracks(artists=artists, count=track_count)
            tracks_href = URL(album_href).joinpath("tracks")
            payload["tracks"] = self.format_items_block(
                url=tracks_href, items=tracks, limit=len(tracks), total=track_count
            )

        if properties:
            payload |= {
                "copyrights": self.generate_copyrights(),
                "external_ids": self.generate_external_ids(),
                "genres": [],  # always empty
                "label": "/".join((self.faker.company() for _ in range(self.faker.random_int(1, 3)))),
                "popularity": self.faker.random_int()
            }

        if self.faker.boolean():
            payload["restrictions"] = self.faker.random_element(("market", "product", "explicit"))

        return payload

    def generate_genres(self) -> Sequence[str]:
        """Return a list of randomly generated genres."""
        return self.faker.random_elements(GENRES)

    ################################################################################
    ## Playlists
    ################################################################################
    def generate_playlist(self) -> dict[str, Any]:
        """Return a randomly generated Spotify API response for a playlist."""
        playlist_id = self.generate_resource_id()
        kind = "playlist"
        playlist_href = self.generate_href(kind, playlist_id)
        owner = self.generate_owner()
        public = self.faker.boolean()
        item_count = self.faker.random_int(0, 200)

        payload = {
            "collaborative": False if public else self.faker.boolean(),
            "description": self.faker.sentence(),
            "external_urls": self.generate_external_urls(kind, playlist_id),
            "followers": self.generate_followers(),
            "href": playlist_href,
            "id": playlist_id,
            "images": self.generate_images(),
            "name": self.faker.name(),
            "owner": owner,
            "primary_color": None,
            "public": self.faker.boolean(),
            "snapshot_id": self.faker.pystr(32, 32),
            "type": kind,
            "uri": self.generate_uri(kind, playlist_id),
        }

        items = self.generate_playlist_items(owner, count=item_count)
        items_href = URL(playlist_href).joinpath("items")
        payload["items"] = self.format_items_block(url=items_href, items=items, limit=len(items), total=item_count)

        return payload

    def generate_playlist_items(
            self, owner: dict[str, Any], count: int = 0
    ) -> list[dict[str, Any]]:
        """Return a list of randomly generated Spotify API responses for playlist items with a given owner."""
        items = self.generate_tracks(count=count)
        additional_fields = {"episode": False, "track": True}

        for item in items:
            item |= additional_fields
            self.format_user_item("item", item)

            added_by = self.faker.random_element((deepcopy(owner), self.generate_owner()))
            added_by.pop("display_name", None)

            item |= {
                "added_by": added_by,
                "is_local": item["track"]["is_local"],
                "primary_color": None,
                "video_thumbnail": {"url": None},
            }

        return items

    ################################################################################
    ## Sub-parts
    ################################################################################
    def generate_resource_id(self) -> str:
        """Return a randomly generated Spotify API resource ID (22-character alphanumeric string)."""
        return self.faker.pystr(22, 22)

    def generate_uri(self, kind: str, resource_id: str = None) -> str:
        """Return a Spotify URI for a given resource kind and ID."""
        if not resource_id:
            resource_id = self.generate_resource_id()
        return f"spotify:{kind}:{resource_id}"

    def generate_href(self, kind: str, resource_id: str = None) -> str:
        """Return a Spotify API URL for a given resource kind and ID."""
        if not resource_id:
            resource_id = self.generate_resource_id()
        return str(URL.build(
            scheme="https", host="api.spotify.com", path=f"/v1/{kind}s/{resource_id}"
        ))

    def generate_external_urls(self, kind: str, resource_id: str = None) -> dict[str, Any]:
        """Return a Spotify external URLs object for a given resource kind and ID."""
        if not resource_id:
            resource_id = self.generate_resource_id()

        return {
            "spotify": str(URL.build(
                scheme="https", host="open.spotify.com", path=f"/{kind}/{resource_id}"
            ))
        }

    def generate_external_ids(self) -> dict[str, Any]:
        """Return a Spotify external IDs object with randomly generated ISRC, RAN, and UPC codes."""
        external_ids = {}

        if self.faker.boolean():
            country = self.faker.country_code("alpha-2")
            registrant = "".join(self.faker.random_letters(3)).upper()
            year = str(self.faker.year())[:-2]
            designation = str(self.faker.random_int(int(10e5), int(10e6 - 1)))
            external_ids["isrc"] = f"{country}{registrant}{year}{designation}"

        if self.faker.boolean():
            external_ids["ran"] = str(self.faker.random_int(int(10e13), int(10e14 - 1)))

        if self.faker.boolean():
            external_ids["upc"] = str(self.faker.random_int(int(10e12), int(10e13 - 1)))

        return external_ids

    def generate_images(self) -> list[dict[str, Any]]:
        """
        Return a list of randomly generated Spotify API responses for images, sorted by height in descending order.
        """
        image_sizes: tuple[int, ...] = tuple([64, 160, 300, 320, 500, 640, 800, 1000])

        def generate_image(size: int = self.faker.random_element(image_sizes)):
            """Return a randomly generated Spotify API response for an image."""
            image_id = self.faker.pystr(40, 40)
            url = URL.build(scheme="http", host="i.scdn.co", path=f"/image/{image_id}")
            return {"url": str(url), "height": size, "width": size}

        images = [generate_image(size) for size in self.faker.random_elements(image_sizes)]
        images.sort(key=lambda x: x["height"], reverse=True)
        return images

    def generate_duration(self, duration_ms: int = None) -> int | dict[str, Any]:
        """Return a randomly generated Spotify API response for a duration response"""
        if not duration_ms:
            duration_ms = self.faker.random_int(int(10e4), int(6 * 10e5))  # 1 second to 10 minutes range

        if self.faker.boolean():
            return {"totalMilliseconds": duration_ms}
        return duration_ms

    def generate_countries(self) -> list[str]:
        """Return a list of randomly generated country codes."""
        return [self.faker.country_code("alpha-2") for _ in range(self.faker.random_int(1, 5))]

    def generate_followers(self) -> dict[str, Any]:
        """Return a randomly generated Spotify API response for followers."""
        return {
            "href": None,
            "total": self.faker.random_int(),
        }

    def generate_copyrights(self) -> list[dict[str, Any]]:
        """Return a list of randomly generated Spotify API responses for copyrights."""
        return [
            {"text": self.faker.pystr(50, 100), "type": i}
            for i in ["C", "P"][:self.faker.random_int(1, 2)]
        ]

    ################################################################################
    ## Utilities
    ################################################################################
    @staticmethod
    def format_next_url(url: URL, offset: int = 0, limit: int = 20) -> URL:
        """Format a `next` style URL for looping through API pages"""
        params: dict[str, Any] = dict(url.query)
        params["offset"] = offset
        params["limit"] = limit

        return url.with_query(params)

    def format_items_block(
            self, url: URL, items: list[dict[str, Any]], offset: int = 0, limit: int = 20, total: int = limit_max
    ) -> dict[str, Any]:
        """Format an items block response from a list of items and a given URL."""
        href = self.format_next_url(url=url, offset=offset, limit=limit)
        limit = min(max(limit, 1), self.limit_max)  # limit must be between 1 and 50

        prev_offset = offset - limit
        prev_url = self.format_next_url(url=url, offset=prev_offset, limit=limit) if prev_offset >= 0 else None
        next_offset = offset + limit
        next_url = self.format_next_url(url=url, offset=next_offset, limit=limit) if next_offset < total else None

        return {
            "href": href,
            "limit": limit,
            "next": next_url,
            "offset": offset,
            "previous": prev_url,
            "total": total,
            "items": items
        }

    def format_user_item(self, kind: str, item: dict[str, Any]) -> dict[str, Any]:
        """
        Format a response to expected response for a 'saved user's...' endpoint type.
        Reformats the item in place with additional fields.
        """
        item_copy = deepcopy(item)
        item.clear()

        added_at = self.faker.past_datetime(date(2008, 10, 7))
        item |= {
            "added_at": added_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
            kind: item_copy
        }

        return item
