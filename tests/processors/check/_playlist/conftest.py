from collections.abc import Generator, Collection, Sequence
from copy import deepcopy
from unittest.mock import patch, Mock

import pytest
from faker import Faker

from mytunes.core._collection import CollectionModel
from mytunes.core._collection.playlist import RemoteMutablePlaylist
from mytunes.core.api import RemoteAPI
from mytunes.core.properties.name import HasName
from mytunes.core.properties.order import Position
from mytunes.core.properties.uri import HasMutableURI
from mytunes.processors.check._playlist.page import PlaylistsPage
from mytunes.processors.match import Matcher
from mytunes.processors.score import NameScorer

PlaylistsPage.wait_after_add = 0


@pytest.fixture
def page(position: Position, collections: Sequence[CollectionModel], api: RemoteAPI) -> PlaylistsPage:
    return PlaylistsPage(position=position, api=api, items=collections)


@pytest.fixture
def collection(collections: list[CollectionModel], faker: Faker) -> CollectionModel:
    return faker.random_element(collections)


@pytest.fixture(autouse=True)
def playlist(page: PlaylistsPage, playlists: list[RemoteMutablePlaylist], faker: Faker) -> RemoteMutablePlaylist:
    playlist = faker.random_element(playlists)
    page._playlists[playlist.uri] = playlist
    page._playlists_initial[playlist.uri] = deepcopy(playlist)
    return playlist


@pytest.fixture
def matcher() -> Matcher:
    return Matcher(scorers=[NameScorer()])


@pytest.fixture(autouse=True)
def mock_match() -> Generator[Mock]:
    def _get_match[T: HasName | HasMutableURI](item: T, others: Collection[T], *_, **__) -> T | None:
        return next((other for other in others if item.name == other.name), None)

    with patch.object(Matcher, "match", side_effect=_get_match) as mock_match:
        yield mock_match
