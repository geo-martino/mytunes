import itertools
import math
from collections.abc import Collection, Sequence, Generator
from unittest.mock import Mock, AsyncMock, patch

import pytest
from faker import Faker
from pytest_mock import MockerFixture

from mytunes._models.api import RemoteAPI
from mytunes._models.api.playlist import PlaylistReadWriteEndpoints
from mytunes._models.collection import CollectionModel
from mytunes._models.collection.playlist import RemoteMutablePlaylist
from mytunes._models.item.track import RemoteTrack
from mytunes.processors.check import Checker
from mytunes.processors.check._page import CheckerPage
from tests.processors.utils import MockCollection
from tests.utils import patch_input


class TestCheckerPause:
    @pytest.fixture
    def model(self, api: RemoteAPI) -> Checker:
        return Checker(api=api)

    @pytest.fixture
    def pages(self, model: Checker, collections: list[CollectionModel]) -> int:
        total = len(collections)
        model.interval = total // 4
        return math.ceil(total / model.interval)

    @pytest.fixture(autouse=True)
    def mock_get_playlist_items(self, tracks: list[RemoteTrack], faker: Faker) -> Generator[Mock]:
        def _random_tracks(*_, **__) -> Sequence[RemoteTrack]:
            return faker.random_elements(tracks)

        with patch.object(
                PlaylistReadWriteEndpoints, "get_all", side_effect=_random_tracks, new_callable=AsyncMock
        ) as mock_get_all:
            yield mock_get_all

    @pytest.fixture
    def mock_pause(self, mocker: MockerFixture) -> Mock:
        return mocker.spy(CheckerPage, "pause")

    @pytest.fixture
    def mock_playlist_links(self, mocker: MockerFixture) -> Mock:
        return mocker.spy(CheckerPage, "_print_playlist_links")

    @pytest.fixture
    def mock_playlist_items(self, mocker: MockerFixture) -> Mock:
        return mocker.spy(CheckerPage, "_print_playlist_items")

    @pytest.fixture
    def mock_teardown_playlists(self, mocker: MockerFixture) -> Mock:
        return mocker.spy(CheckerPage, "teardown_playlists")

    @staticmethod
    def assert_pause_calls(
            model: Checker,
            inputs: Sequence[str],
            pages: int,
            names: Collection[str],
            mock_pause: Mock,
            mock_playlist_links: Mock,
            mock_playlist_items: Mock,
            mock_teardown_playlists: Mock,
    ):
        inputs = list(inputs)

        if "q" in inputs:
            inputs = inputs[:inputs.index("q") + 1]

        if inputs.count("") >= pages:
            index = 0
            count = 1

            while count < pages:
                index = inputs.index("", index) + 1
                count += 1

            inputs = inputs[:index + 1]

        expected_pages = min(pages, inputs.count("") + inputs.count("q") + inputs.count("s"))
        expected_help = expected_pages + inputs.count("h")

        names = {name.casefold() for name in names}
        expected_playlist_items = sum(val.casefold() in names for val in inputs)
        expected_playlist_links = inputs.count("l")

        assert mock_pause.call_count == expected_pages
        assert mock_playlist_links.call_count == expected_playlist_links
        assert mock_playlist_items.call_count == expected_playlist_items
        assert mock_teardown_playlists.call_count == expected_pages

    ###########################################################################
    ## Tests
    ###########################################################################
    async def test_pages(
            self,
            model: Checker,
            collections: list[MockCollection],
            pages: int,
            mock_pause: Mock,
            mock_playlist_links: Mock,
            mock_playlist_items: Mock,
            mock_teardown_playlists: Mock,
    ):
        inputs = [""] * pages + ["h"] + ["invalid_input"]  # add some other random inputs
        with patch_input(iter(inputs)):
            await model.check(collections)

        self.assert_pause_calls(
            model,
            inputs=inputs,
            pages=pages,
            names={coll.name for coll in collections},
            mock_pause=mock_pause,
            mock_playlist_links=mock_playlist_links,
            mock_playlist_items=mock_playlist_items,
            mock_teardown_playlists=mock_teardown_playlists,
        )

    async def test_pause_prints_help(
            self,
            model: Checker,
            collections: list[MockCollection],
            pages: int,
            mock_pause: Mock,
            mock_playlist_links: Mock,
            mock_playlist_items: Mock,
            mock_teardown_playlists: Mock,
    ):
        inputs = ["h", "h", "", "h", "", "h"] + [""] * pages
        with patch_input(iter(inputs)):
            await model.check(collections)

        self.assert_pause_calls(
            model,
            inputs=inputs,
            pages=pages,
            names={coll.name for coll in collections},
            mock_pause=mock_pause,
            mock_playlist_links=mock_playlist_links,
            mock_playlist_items=mock_playlist_items,
            mock_teardown_playlists=mock_teardown_playlists,
        )

    async def test_pause_skips(
            self,
            model: Checker,
            collections: list[MockCollection],
            pages: int,
            mock_pause: Mock,
            mock_playlist_links: Mock,
            mock_playlist_items: Mock,
            mock_teardown_playlists: Mock,
    ):
        inputs = ["", "h", "", "s", "h"] + [""] * pages
        with patch_input(iter(inputs)):
            await model.check(collections)

        self.assert_pause_calls(
            model,
            inputs=inputs,
            pages=pages,
            names={coll.name for coll in collections},
            mock_pause=mock_pause,
            mock_playlist_links=mock_playlist_links,
            mock_playlist_items=mock_playlist_items,
            mock_teardown_playlists=mock_teardown_playlists,
        )

    async def test_pause_quits(
            self,
            model: Checker,
            collections: list[MockCollection],
            pages: int,
            mock_pause: Mock,
            mock_playlist_links: Mock,
            mock_playlist_items: Mock,
            mock_teardown_playlists: Mock,
    ):
        inputs = ["", "h", "", "q"]
        with patch_input(iter(inputs)):
            await model.check(collections)

        self.assert_pause_calls(
            model,
            inputs=inputs,
            pages=pages,
            names={coll.name for coll in collections},
            mock_pause=mock_pause,
            mock_playlist_links=mock_playlist_links,
            mock_playlist_items=mock_playlist_items,
            mock_teardown_playlists=mock_teardown_playlists,
        )

    async def test_pause_print_playlist(
            self,
            model: Checker,
            collections: list[MockCollection],
            playlists: list[RemoteMutablePlaylist],
            pages: int,
            mock_get_playlist_items: Mock,
            mock_pause: Mock,
            mock_playlist_links: Mock,
            mock_playlist_items: Mock,
            mock_teardown_playlists: Mock,
            faker: Faker,
    ):
        playlist_names = (
            faker.random_element({pl.name, pl.name.lower(), pl.name.title(), pl.name.upper()})
            for pl in playlists
        )
        playlist_name_groups = list(itertools.batched(playlist_names, model.interval))

        inputs = [
            "",  # move to page 2
            "l",
            faker.random_element(playlist_name_groups[1]),  # select from page 2
            "l",
            "",  # move to page 3
            faker.random_element(playlist_name_groups[2]),  # select from page 3
            "l",
            "l",
            "",  # move to page 4
            "q",
        ]

        with patch_input(iter(inputs)):
            await model.check(collections)

        self.assert_pause_calls(
            model,
            inputs=inputs,
            pages=pages,
            names={coll.name for coll in collections},
            mock_pause=mock_pause,
            mock_playlist_links=mock_playlist_links,
            mock_playlist_items=mock_playlist_items,
            mock_teardown_playlists=mock_teardown_playlists,
        )

        # assert explicitly to be sure
        assert mock_playlist_links.call_count == 4
        assert mock_playlist_items.call_count == 2
