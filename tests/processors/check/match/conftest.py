from collections.abc import Generator, Collection
from copy import deepcopy
from functools import total_ordering
from typing import ClassVar
from unittest.mock import patch, Mock, AsyncMock

import pytest
from faker import Faker

from musify._models import ResourceModel
from musify._models.api import RemoteAPI
from musify._models.api.playlist import PlaylistReadWriteEndpoints
from musify._models.collection import CollectionModel
from musify._models.collection.playlist import RemoteMutablePlaylist
from musify._models.item.genre import Genre
from musify._models.item.track import Track
from musify._models.properties.name import HasName
from musify._models.properties.order import Position
from musify._models.properties.uri import HasMutableURI, HasImmutableURI, HasURI
from musify.processors.check._page import CheckerPage
from musify.processors.match import Matcher
from tests.processors.utils import MockCollection
from tests.remote import SimpleURI, MockUrlCursor

CheckerPage.wait_after_add = 0


@pytest.fixture
def page(position: Position, collections: Collection[CollectionModel], api: RemoteAPI) -> CheckerPage:
    return CheckerPage(position=position, api=api, collections=collections)


@pytest.fixture(autouse=True)
def playlist(page: CheckerPage, playlist: RemoteMutablePlaylist) -> RemoteMutablePlaylist:
    page._playlists[playlist.uri] = playlist
    page._playlists_initial[playlist.uri] = deepcopy(playlist)
    return playlist


@pytest.fixture(autouse=True)
def collection(
        page: CheckerPage,
        playlist: RemoteMutablePlaylist,
        available_items: list[HasURI],
        unavailable_items: list[HasURI],
        missing_items: list[HasURI],
        invalid_items: list[ResourceModel],
        mutable_items: list[HasMutableURI],
        faker: Faker,
) -> CollectionModel:
    collection = MockCollection(
        name=playlist.name,
        cursor=MockUrlCursor(url=faker.url()),
        uri=SimpleURI.create_random(MockCollection.type),
        all_items=available_items + unavailable_items + missing_items + invalid_items + mutable_items
    )
    page._collections[playlist.uri] = collection
    return collection


@total_ordering
class HasNameAndImmutableURI(HasName, HasImmutableURI):
    type: ClassVar[str] = Track.type
    name: str

    def __eq__(self, other: object) -> bool:  # make equality check on just names work
        if not isinstance(other, HasNameAndImmutableURI) and not (isinstance(other, HasNameAndMutableURI)):
            return super().__eq__(other)
        return self.uri == other.uri or self.name == other.name

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, HasNameAndImmutableURI) and not (isinstance(other, HasNameAndMutableURI)):
            return super().__lt__(other)
        return self.name < other.name


@total_ordering
class HasNameAndMutableURI(HasName, HasMutableURI):
    type: ClassVar[str] = Track.type
    name: str

    def __eq__(self, other: object) -> bool:  # make equality check on just names work
        if not isinstance(other, HasNameAndImmutableURI) and not (isinstance(other, HasNameAndMutableURI)):
            return super().__eq__(other)
        return self.uri == other.uri or self.name == other.name

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, HasNameAndImmutableURI) and not (isinstance(other, HasNameAndMutableURI)):
            return super().__lt__(other)
        return self.name < other.name


@pytest.fixture
def available_items(faker: Faker) -> list[HasImmutableURI]:
    return [
        HasNameAndImmutableURI(name=faker.name(), uri=SimpleURI.create_random(Track.type))
        for _ in range(faker.random_int(10, 30))
    ]


@pytest.fixture
def mutable_items(faker: Faker) -> list[HasMutableURI]:
    return [
        HasNameAndMutableURI(name=faker.name(), uri=SimpleURI.create_random(Track.type))
        for _ in range(faker.random_int(10, 30))
    ]


@pytest.fixture
def unavailable_items(faker: Faker) -> list[HasMutableURI]:
    return [
        HasNameAndMutableURI(name=faker.name(), uri=SimpleURI.create_unavailable(Track.type))
        for _ in range(faker.random_int(5, 20))
    ]


@pytest.fixture
def missing_items(faker: Faker) -> list[HasMutableURI]:
    missing = [
        HasNameAndMutableURI(name=faker.name(), uri=None)
        for _ in range(faker.random_int(10, 30))
    ]

    return missing


@pytest.fixture
def invalid_items(faker: Faker) -> list[Genre]:
    return [Genre(name=faker.name()) for _ in range(faker.random_int(5, 20))]


@pytest.fixture(autouse=True)
def mock_get_playlist_items(available_items: list[HasURI], faker: Faker) -> Generator[Mock, None, None]:
    with patch.object(
            PlaylistReadWriteEndpoints, "get_all", return_value=available_items, new_callable=AsyncMock
    ) as mock_get_all:
        yield mock_get_all


@pytest.fixture(autouse=True)
def mock_match() -> Generator[Mock, None, None]:
    def _get_match[T: HasName | HasMutableURI](item: T, others: Collection[T], *_, **__) -> T | None:
        return next((other for other in others if item.name == other.name), None)

    with patch.object(Matcher, "match", side_effect=_get_match) as mock_match:
        yield mock_match
