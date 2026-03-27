from collections.abc import Collection
from copy import deepcopy
from typing import Generator
from unittest.mock import Mock, patch, AsyncMock

import pytest
from faker import Faker
from pytest_mock import MockerFixture

from musify.models import ResourceModel
from musify.models.api import RemoteAPI
from musify.models.api.playlist import PlaylistReadWriteEndpoints
from musify.models.collection import CollectionModel
from musify.models.collection.playlist import Playlist, RemoteMutablePlaylist
from musify.models.item.genre import Genre
from musify.models.item.track import Track
from musify.models.properties.name import HasName
from musify.models.properties.uri import HasURI, HasImmutableURI, HasMutableURI
from musify.processors_new.check import Checker, CheckResult
from musify.processors_new.match import Matcher
from tests.models.api.utils import MockUrlCursor
from tests.processors_new.check.utils import HasNameAndImmutableURI, HasNameAndMutableURI
from tests.processors_new.utils import MockCollection
from tests.utils import SimpleURI, split_list


class TestMatchWithInput:
    @pytest.fixture
    def model(self, api: RemoteAPI) -> Checker:
        return Checker(api=api)

    @pytest.fixture(autouse=True)
    def playlist(self, model: Checker, playlist: RemoteMutablePlaylist) -> RemoteMutablePlaylist:
        model._playlists[playlist.uri] = playlist
        model._playlists_initial[playlist.uri] = deepcopy(playlist)
        return playlist

    @pytest.fixture(autouse=True)
    def collection(
            self,
            model: Checker,
            playlist: Playlist,
            available_items: list[HasURI],
            unavailable_items: list[HasURI],
            missing_items: list[HasURI],
            invalid_items: list[ResourceModel],
            faker: Faker,
    ) -> CollectionModel:
        collection = MockCollection(
            name=playlist.name,
            cursor=MockUrlCursor(url=faker.url()),
            uri=SimpleURI.create_random(MockCollection.type),
            all_items=available_items + unavailable_items + missing_items + invalid_items
        )
        model._collections[playlist.uri] = collection
        return collection

    @pytest.fixture
    def available_items(self, faker: Faker) -> list[HasImmutableURI]:
        return [
            HasNameAndImmutableURI(name=faker.name(), uri=SimpleURI.create_random(Track.type))
            for _ in range(faker.random_int(10, 30))
        ]

    @pytest.fixture
    def mutable_uri_items(self, faker: Faker) -> list[HasMutableURI]:
        return [
            HasNameAndMutableURI(name=faker.name(), uri=SimpleURI.create_random(Track.type))
            for _ in range(faker.random_int(10, 30))
        ]

    @pytest.fixture
    def unavailable_items(self, faker: Faker) -> list[HasImmutableURI]:
        return [
            HasNameAndImmutableURI(name=faker.name(), uri=SimpleURI.create_unavailable(Track.type))
            for _ in range(faker.random_int(5, 20))
        ]

    @pytest.fixture
    def missing_items(self, faker: Faker) -> list[HasImmutableURI]:
        missing = [
            HasNameAndImmutableURI(name=faker.name(), uri=None)
            for _ in range(faker.random_int(5, 20))
        ]

        for item in missing:
            item.__dict__["has_uri"] = None  # force missing URI

        return missing

    @pytest.fixture
    def invalid_items(self, faker: Faker) -> list[Genre]:
        return [Genre(name=faker.name()) for _ in range(faker.random_int(5, 20))]

    @pytest.fixture(autouse=True)
    def mock_get_playlist_items(self, available_items: list[HasURI], faker: Faker) -> Generator[Mock, None, None]:
        with patch.object(
                PlaylistReadWriteEndpoints, "get_all", return_value=available_items, new_callable=AsyncMock
        ) as mock_get_all:
            yield mock_get_all
