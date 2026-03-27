from collections.abc import Iterable
from random import choice, randrange
from typing import Any

from musify.libraries.remote.core.types import RemoteIDType, RemoteObjectType
from musify.libraries.remote.core.wrangle import RemoteDataWrangler
from musify.libraries.remote.spotify.base import SpotifyObject
from musify.libraries.remote.spotify.wrangle import SpotifyDataWrangler
from tests.libraries.remote.core.utils import ALL_ID_TYPES
from tests.utils import random_str


def random_id() -> str:
    """Generates a valid looking random Spotify ID"""
    return random_str(RemoteIDType.ID.value, RemoteIDType.ID.value)


def random_ids(start: int = 1, stop: int = 50) -> list[str]:
    """Generates many valid looking random Spotify IDs"""
    range_ = randrange(start=start, stop=stop) if start < stop else start
    return [random_id() for _ in range(range_)]


def random_id_type(wrangler: RemoteDataWrangler, kind: RemoteObjectType, id_: str | None = None) -> str:
    """Convert the given ``id_`` to a random ID type"""
    type_in = RemoteIDType.ID
    type_out = choice(ALL_ID_TYPES)
    return wrangler.convert(id_ or random_id(), kind=kind, type_in=type_in, type_out=type_out)


def random_id_types(
        wrangler: RemoteDataWrangler,
        kind: RemoteObjectType,
        id_list: Iterable[str] | None = None,
        start: int = 1,
        stop: int = 10
) -> list[str]:
    """Generate list of random ID types based on input item type"""
    if id_list:
        pass
    elif kind == RemoteObjectType.USER:
        id_list = [random_str(1, RemoteIDType.ID.value - 1) for _ in range(randrange(start=start, stop=stop))]
    else:
        id_list = random_ids(start=start, stop=stop)

    return [random_id_type(id_=id_, wrangler=wrangler, kind=kind) for id_ in id_list]


def random_uri(kind: RemoteObjectType = RemoteObjectType.TRACK) -> str:
    """Generates a valid looking random Spotify URI of item :py:class:`RemoteObjectType` ``kind``"""
    return f"{SpotifyDataWrangler.source.lower()}:{kind.name.lower()}:{random_id()}"


def random_uris(kind: RemoteObjectType = RemoteObjectType.TRACK, start: int = 1, stop: int = 50) -> list[str]:
    """Generates many valid looking random Spotify URIs of item :py:class:`RemoteObjectType` ``kind``"""
    range_ = randrange(start=start, stop=stop) if start < stop else start
    return [random_uri(kind=kind) for _ in range(range_)]


def random_api_url(kind: RemoteObjectType = RemoteObjectType.TRACK) -> str:
    """Generates a valid looking random Spotify API URL of item :py:class:`RemoteObjectType` ``kind``"""
    return f"{SpotifyDataWrangler.url_api}/{kind.name.lower()}s/{random_id()}"


def random_api_urls(kind: RemoteObjectType = RemoteObjectType.TRACK, start: int = 1, stop: int = 50) -> list[str]:
    """Generates many valid looking random Spotify API URLs of item :py:class:`RemoteObjectType` ``kind``"""
    range_ = randrange(start=start, stop=stop) if start < stop else start
    return [random_api_url(kind=kind) for _ in range(range_)]


def random_ext_url(kind: RemoteObjectType = RemoteObjectType.TRACK) -> str:
    """Generates a valid looking random Spotify external URL of item :py:class:`RemoteObjectType` ``kind``"""
    return f"{SpotifyDataWrangler.url_ext}/{kind.name.lower()}/{random_id()}"


def random_ext_urls(kind: RemoteObjectType = RemoteObjectType.TRACK, start: int = 1, stop: int = 50) -> list[str]:
    """Generates many valid looking random Spotify external URLs of item :py:class:`RemoteObjectType` ``kind``"""
    range_ = randrange(start=start, stop=stop) if start < stop else start
    return [random_ext_url(kind=kind) for _ in range(range_)]


def assert_id_attributes(item: SpotifyObject, response: dict[str, Any]):
    """Check a given :py:class:`SpotifyObject` has the expected attributes relating to its identification"""
    assert item.has_uri
    assert item.uri == response["uri"]
    assert item.id == response["id"]
    assert str(item.url) == response["href"]
    assert str(item.url_ext) == response["external_urls"]["spotify"]
