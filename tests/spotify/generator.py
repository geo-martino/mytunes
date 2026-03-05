from collections.abc import Sequence
from copy import deepcopy
from datetime import date
from typing import Any

from faker import Faker
from yarl import URL

from tests.utils import GENRES


class SpotifyPayloadGenerator:
    """Utility class for generating random Spotify API responses for testing purposes."""
    limit_max = 50  # maximum limit for Spotify API pagination

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
    def generate_track(self) -> dict[str, Any]:
        """Return a randomly generated Spotify API response for a track."""
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

        return payload

    def add_track_extended_properties(self, payload: dict[str, Any]) -> None:
        """Add extended properties to a track payload in-place."""
        album = self.generate_album()
        artists = [self.generate_artist() for _ in range(self.faker.random_int(1, 5))]
        self.add_album_artists(payload, artists)

        payload |= {
            "album": album,
            "artists": artists,
        }

    def generate_tracks(
            self, album: dict[str, Any] = None, artists: list[dict[str, Any]] = None, count: int = 0
    ) -> list[dict[str, Any]]:
        """Randomly generate tracks for a given album and set of artists."""
        if count == 0:
            if album:
                count = album["total_tracks"]
            else:
                count = self.faker.random_int(1, 30)

        tracks = [self.generate_track() for _ in range(count)]

        for position, track in enumerate(tracks, 1):
            track["track_number"] = position
            track.pop("popularity", None)

            if artists:
                track["artists"] = deepcopy(artists)
            if album:
                track["album"] = deepcopy(album)

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
        duration_ms = self.faker.random_int(int(10e4), int(6 * 10e5))  # 1 second to 10 minutes range
        return {"track": {"duration": duration_ms / 1000}}

    ################################################################################
    ## Artists
    ################################################################################
    def generate_artist(self) -> dict[str, Any]:
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

        return payload

    def add_artist_extended_properties(self, payload: dict[str, Any]) -> None:
        """Add extended properties to an artist payload in-place."""
        payload |= {
            "followers": self.generate_followers(),
            "genres": self.generate_genres(),
            "images": self.generate_images(),
            "popularity": self.faker.random_int(0, 100),
        }

    def add_artist_albums(self, payload: dict[str, Any], albums: list[dict[str, Any]] = None, count: int = 0) -> None:
        """Add albums to an artist payload in-place."""
        if not albums:
            albums = []
            if count == 0:
                count = self.faker.random_int(1, 10)

        for _ in range(count):
            album = self.generate_album()
            self.add_album_artists(album, artists=[payload], count=self.faker.random_int(0, 3))
            albums.append(album)

        artist_href = payload["href"]
        albums_href = URL(artist_href).joinpath("albums")
        payload["albums"] = self.format_items_block(
            url=albums_href, items=albums, limit=len(albums), total=len(albums)
        )

    ################################################################################
    ## Album generators
    ################################################################################
    def generate_album(self) -> dict[str, Any]:
        """Return a randomly generated Spotify API response for an album."""
        album_id = self.generate_resource_id()
        kind = "album"
        album_href = self.generate_href("album", album_id)
        track_count = self.faker.random_int(1, 30)

        payload = {
            "album_type": self.faker.random_element(("album", "single", "compilation")),
            "total_tracks": track_count,
            "available_markets": self.generate_countries(),
            "external_urls": self.generate_external_urls(kind, album_id),
            "href": album_href,
            "id": album_id,
            "images": self.generate_images(),
            "name": self.faker.name(),
            **self.generate_release_date(),
            "type": kind,
            "uri": self.generate_uri(kind, album_id),
        }

        if self.faker.boolean():
            payload["restrictions"] = self.generate_restrictions()

        return payload

    def add_album_artists(self, payload: dict[str, Any], artists: list[dict[str, Any]] = None, count: int = 0) -> None:
        """Add artists to an album payload in-place."""
        if not artists:
            artists = []
            if count == 0:
                count = self.faker.random_int(1, 5)

        artists.extend(self.generate_artist() for _ in range(count))

        payload["artists"] = artists

    def add_album_extended_properties(self, payload: dict[str, Any]) -> None:
        """Add extended properties to an album payload in-place."""
        payload |= {
            "copyrights": self.generate_copyrights(),
            "external_ids": self.generate_external_ids(),
            "genres": [],  # always empty
            "label": "/".join((self.faker.company() for _ in range(self.faker.random_int(1, 3)))),
            "popularity": self.faker.random_int(1, 100)
        }

    def add_album_tracks(self, payload: dict[str, Any]) -> None:
        """Add tracks to an album payload in-place."""
        artists = payload["artists"]
        track_count = payload["total_tracks"]
        album_href = payload["href"]

        tracks = self.generate_tracks(artists=artists, count=track_count)
        tracks_href = URL(album_href).joinpath("tracks")
        payload["tracks"] = self.format_items_block(
            url=tracks_href, items=tracks, limit=len(tracks), total=track_count
        )

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

        return payload

    def add_playlist_items(self, payload: dict[str, Any], count: int = 0) -> None:
        """Add items to a playlist payload in-place."""
        owner = payload["owner"]
        playlist_href = payload["href"]

        items = self._generate_playlist_items(owner, count=count)
        items_href = URL(playlist_href).joinpath("items")
        payload["items"] = self.format_items_block(url=items_href, items=items, limit=len(items), total=count)

    def _generate_playlist_items(
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
            if self.faker.boolean():
                added_by = None  # some very old playlists may return null in this field

            item |= {
                "added_by": added_by,
                "is_local": item["item"]["is_local"],
                "primary_color": None,
                "video_thumbnail": {"url": None},
            }

        return items

    ###########################################################################
    ## Shows + Episodes
    ###########################################################################
    def generate_show(self) -> dict[str, Any]:
        """Return a randomly generated Spotify API response for a Show."""
        kind = "show"
        show_id = self.generate_resource_id()
        episode_count = self.faker.random_int(1, 30)

        # noinspection PyTypeChecker
        payload = {
            "available_markets": self.generate_countries(),
            "copyrights": self.generate_copyrights(),
            "description": self.faker.sentence(),
            "html_description": self.faker.sentence(),
            "explicit": self.faker.random_element((self.faker.boolean(), None)),
            "external_urls": self.generate_external_urls(kind, show_id),
            "href": self.generate_href(kind, show_id),
            "id": show_id,
            "images": self.generate_images(),
            "is_externally_hosted": self.faker.random_element((self.faker.boolean(), None)),
            "languages": map(str.lower, self.generate_countries()),
            "media_type": self.faker.choice(("audio", "video", "mixed")),
            "name": self.faker.name(),
            "publisher": self.faker.company(),
            "type": kind,
            "uri": self.generate_uri(kind, show_id),
            "total_episodes": episode_count,
        }

        if self.faker.boolean():
            payload["restrictions"] = self.generate_restrictions()

        return payload

    def add_show_episodes(self, payload: dict[str, Any]) -> None:
        """Add episodes to a show payload in-place."""
        episode_count = payload["total_episodes"]
        show_href = payload["href"]

        episodes = self.generate_episodes(show=payload)
        episodes_href = URL(show_href).joinpath("episodes")
        payload["episodes"] = self.format_items_block(
            url=episodes_href, items=episodes, limit=len(episodes), total=episode_count
        )

    def generate_episode(self) -> dict[str, Any]:
        """Return a randomly generated Spotify API response for an Episode."""
        kind = "episode"
        episode_id = self.generate_resource_id()
        duration_ms = self.faker.random_int(int(10e4), int(3.6*10e6))  # 1 second to 1 hour range
        languages = self.generate_countries() 

        payload = {
            "audio_preview_url": self.faker.random_element((self.generate_audio_preview_url(episode_id), None)),
            "description": self.faker.sentence(),
            "html_description": self.faker.sentence(),
            "duration_ms": duration_ms,
            "explicit": self.faker.random_element((self.faker.boolean(), None)),
            "external_urls": self.generate_external_urls(kind, episode_id),
            "href": self.generate_href(kind, episode_id),
            "id": episode_id,
            "images": self.generate_images(),
            "is_externally_hosted": self.faker.boolean(),
            "is_playable": self.faker.boolean(),
            "language": self.faker.random_element(languages),
            "languages": languages,
            "name": self.faker.name(),
            **self.generate_release_date(),
            "resume_point": self.generate_resume_point(duration_ms),
            "type": kind,
            "uri": self.generate_uri(kind, episode_id),
        }

        if self.faker.boolean():
            payload["restrictions"] = self.generate_restrictions()

        return payload

    def generate_episodes(self, show: dict[str, Any], count: int = 0) -> list[dict[str, Any]]:
        """Randomly generate tracks for a given album and set of artists."""
        if count == 0:
            if show:
                count = show["total_episodes"]
            else:
                count = self.faker.random_int(1, 30)

        episodes = [self.generate_episode() for _ in range(count)]

        for episode in episodes:
            if show:
                episode["languages"] = show["languages"]

        return episodes

    def add_episode_show(self, episode: dict[str, Any], show: dict[str, Any] = None) -> dict[str, Any]:
        """Add show information to an episode payload in-place."""
        if not show:
            show = self.generate_show()

        episode["show"] = deepcopy(show)

        return episode

    def add_episodes_show(self, episodes: list[dict[str, Any]], show: dict[str, Any] = None) -> list[dict[str, Any]]:
        """Add show information to a list of episode payloads in-place."""
        if not show:
            show = self.generate_show()

        for episode in episodes:
            self.add_episode_show(episode, show)

        return episodes

    ###########################################################################
    ## Audiobooks + Chapters
    ###########################################################################
    def generate_audiobook(self) -> dict[str, Any]:
        """Return a randomly generated Spotify API response for an Audiobook."""
        kind = "audiobook"
        audiobook_id = self.generate_resource_id()
        chapter_count = self.faker.random_int(1, 20)

        response = {
            "authors": [{"name": self.faker.name()} for _ in range(self.faker.random_int(1, 5))],
            "available_markets": self.generate_countries(),
            "copyrights": self.generate_copyrights(),
            "description": self.faker.sentence(),
            "html_description": self.faker.sentence(),
            "edition": self.faker.word(),
            "explicit": self.faker.random_element((self.faker.boolean(), None)),
            "external_urls": self.generate_external_urls(kind, audiobook_id),
            "href": self.generate_href(kind, audiobook_id),
            "id": audiobook_id,
            "images": self.generate_images(),
            "languages": self.generate_countries(),
            "media_type": "audio",
            "name": self.faker.company(),
            "narrators": [{"name": self.faker.name()} for _ in range(self.faker.random_int(1, 10))],
            "publisher": self.faker.company(),
            "type": kind,
            "uri": self.generate_uri(kind, audiobook_id),
            "total_chapters": chapter_count,
        }

        return response

    def add_audiobook_chapters(self, payload: dict[str, Any]) -> None:
        """Add chapters to an audiobook payload in-place."""
        chapter_count = payload["total_chapters"]
        audiobook_href = payload["href"]

        chapters = self.generate_chapters(audiobook=payload)
        chapters_href = URL(audiobook_href).joinpath("chapters")
        payload["chapters"] = self.format_items_block(
            url=chapters_href, items=chapters, limit=len(chapters), total=chapter_count
        )

    def generate_chapter(self, chapter_number: int = None) -> dict[str, Any]:
        """Return a randomly generated Spotify API response for a Chapter."""
        kind = "chapter"
        chapter_id = self.generate_resource_id()
        duration_ms = self.faker.random_int(int(10e4), int(6*10e5))  # 1 second to 10 minutes range

        response = {
            "audio_preview_url": self.faker.random_element((self.generate_audio_preview_url(chapter_id), None)),
            "available_markets": self.generate_countries(),
            "chapter_number": chapter_number or self.faker.random_int(0, 20),
            "description": self.faker.sentence(),
            "html_description": self.faker.sentence(),
            "duration_ms": duration_ms,
            "explicit": self.faker.random_element((self.faker.boolean(), None)),
            "external_urls": self.generate_external_urls(kind, chapter_id),
            "href": self.generate_href(kind, chapter_id),
            "id": chapter_id,
            "images": self.generate_images(),
            "is_playable": self.faker.boolean(),
            "languages": self.generate_countries(),
            "name": self.faker.name(),
            **self.generate_release_date(),
            "resume_point": self.generate_resume_point(duration_ms),
            "type": kind,
            "uri": self.generate_uri(kind, chapter_id),
        }

        return response

    def generate_chapters(self, audiobook: dict[str, Any], count: int = 0) -> list[dict[str, Any]]:
        """Randomly generate tracks for a given album and set of artists."""
        if count == 0:
            if audiobook:
                count = audiobook["total_chapters"]
            else:
                count = self.faker.random_int(1, 30)

        chapters = [self.generate_chapter() for _ in range(count)]

        for position, chapter in enumerate(chapters, 1):
            chapter["chapter_number"] = position

            if audiobook:
                chapter["languages"] = audiobook["languages"]

        return chapters

    def add_chapter_audiobook(self, chapter: dict[str, Any], audiobook: dict[str, Any] = None) -> dict[str, Any]:
        """Add audiobook information to a chapter payload in-place."""
        if not audiobook:
            audiobook = self.generate_show()

        chapter["audiobook"] = deepcopy(audiobook)

        return chapter

    def add_chapters_audiobook(
            self, chapters: list[dict[str, Any]], audiobook: dict[str, Any] = None
    ) -> list[dict[str, Any]]:
        """Add audiobook information to a list of chapter payloads in-place."""
        if not audiobook:
            audiobook = self.generate_audiobook()

        for chapter in chapters:
            self.add_episode_show(chapter, audiobook)

        return chapters

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

    def generate_release_date(self) -> dict[str, Any]:
        """Return a randomly generated Spotify API response for a release date, with random precision."""
        return {
            "release_date": self.faker.past_date(date(1990, 1, 1)).isoformat(),
            "release_date_precision": self.faker.random_element(("year", "month", "day")),
        }

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

    def generate_restrictions(self) -> str:
        """Return a randomly generated Spotify API restriction reason."""
        return self.faker.random_element(("market", "product", "explicit"))

    def generate_audio_preview_url(self, resource_id: str) -> str:
        """Return a randomly generated Spotify API response for an audio preview URL."""
        return str(URL.build(
            scheme="https",
            host="podz-content.spotifycdn.com",
            path=f"/audio/clips/{resource_id}/{self.faker.uuid4()}.mp3"
        ))

    def generate_resume_point(self, duration_ms: int) -> dict[str, Any]:
        """Return a randomly generated Spotify API response for a resume point."""
        return {
            "fully_played": self.faker.boolean(),
            "resume_position_ms": self.faker.random_int(0, duration_ms),
        }

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
            "items": items[:limit]
        }

    def format_user_item(self, kind: str, item: dict[str, Any]) -> dict[str, Any]:
        """
        Format a response to expected response for a 'saved user's...' endpoint type.
        Reformats the item in place with additional fields.
        """
        item_copy = deepcopy(item)
        item.clear()

        added_at = self.faker.past_datetime(date(2008, 10, 7)).strftime("%Y-%m-%dT%H:%M:%SZ")
        if self.faker.boolean():
            added_at = None  # some very old playlists may return null in this field

        item |= {
            "added_at": added_at,
            kind: item_copy
        }

        return item
