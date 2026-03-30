import itertools
import math
import re
from collections.abc import Collection, Iterator, Callable
from random import choice
from typing import Self, final

from faker import Faker
from pydantic_core.core_schema import ValidatorFunctionWrapHandler
from yarl import URL

from musify.models.collection.playlist import Playlist
from musify.models.item.album import Album
from musify.models.item.artist import Artist
from musify.models.item.track import Track
from musify.models.properties.uri import URI

# noinspection SpellCheckingInspection
GENRES: tuple[str, ...] = tuple(genre.lower() for genre in (
    "Adult Contemporary",
    "Arab Pop",
    "Baroque",
    "Britpop",
    "Bubblegum Pop",
    "Chamber Pop",
    "Chanson",
    "Christian Pop",
    "Classical Crossover",
    "Europop",
    "Dance Pop",
    "Dream Pop",
    "Electro Pop",
    "Iranian Pop",
    "Jangle Pop",
    "Latin Ballad",
    "Levenslied",
    "Louisiana Swamp Pop",
    "Mexican Pop",
    "Motorpop",
    "New Romanticism",
    "Orchestral Pop",
    "Pop Rap",
    "Popera",
    "Pop/Rock",
    "Pop Punk",
    "Power Pop",
    "Psychedelic Pop",
    "Schlager",
    "Soft Rock",
    "Sophisti-Pop",
    "Space Age Pop",
    "Sunshine Pop",
    "Surf Pop",
    "Synthpop",
    "Teen Pop",
    "Traditional Pop Music",
    "Turkish Pop",
    "Vispop",
    "Wonky Pop"
))


def split_list[T](lst: Collection[T], n: int = None, overlap: int = 0) -> Iterator[list[T]]:
    """
    Split a list into n sub-lists of approximately equal size.

    :param lst: The list to split.
    :param n: The number of sub-lists to create.
    :param overlap: The number of overlapping elements between sub-lists.
    """
    if n is None:
        n = choice(range(1, len(lst) + 1))
    if overlap >= len(lst):
        raise ValueError("Overlap must be less than the size of the list.")

    def _get_batcher():
        # noinspection PyTypeChecker
        return map(list, itertools.batched(lst, size))

    size = math.ceil((len(lst) + 1) / n)
    batcher_left = _get_batcher()
    batcher_right = _get_batcher()
    next(batcher_right)

    overlap_result = []
    # noinspection PyTypeChecker
    for item in batcher_left:
        overlap_batch = next(batcher_right, [])[:overlap]
        overlap_result.extend(overlap_batch)
        yield item + overlap_batch

    if overlap:
        yield overlap_result


@final
class SimpleURI(URI):
    __final__ = True
    _source = "remote"

    @property
    def source(self) -> str:
        return self.root.split(":")[0]

    @property
    def type(self) -> str:
        return self.root.split(":")[1]

    @property
    def id(self) -> str:
        return self.root.split(":")[2]

    @classmethod
    def create_random(cls, kind: str | None = None) -> Self:
        if not kind:
            kind = choice((Track.type, Album.type, Artist.type, Playlist.type))
        value = Faker().pystr()
        return cls.from_id(value=value, kind=kind)

    @classmethod
    def create_unavailable(cls, kind: str) -> Self:
        return cls.from_id(value=cls._unavailable_id, kind=kind)

    @classmethod
    def from_id[T](cls, value: T, kind: str) -> T | Self:
        uri = ":".join((cls._source, kind, str(value)))
        return cls(uri)

    @property
    def api_url(self) -> URL:
        return URL.build(scheme="https", host="api.example.com", path=f"/{self.type}/{self.id}")

    @classmethod
    def from_api_url[T](cls, value: T, handler: ValidatorFunctionWrapHandler) -> T | Self:
        return cls.from_public_url(value, handler)

    @property
    def public_url(self) -> URL:
        return URL.build(scheme="https", host="example.com", path=f"/{self.type}/{self.id}")

    @classmethod
    def from_public_url[T](cls, value: T, handler: ValidatorFunctionWrapHandler) -> T | Self:
        if isinstance(value, str) and re.match(r"^https://(api.)?example\.com", value):
            value = URL(value)
        if not isinstance(value, URL):
            return value

        uri = ":".join((cls._source, *value.path.lstrip("/").split("/")[-2:]))
        return handler(uri)


def assert_validator_skips[T](func: Callable[[T], T], value: T):
    assert func(value) is value
