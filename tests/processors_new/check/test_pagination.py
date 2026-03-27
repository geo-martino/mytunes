import itertools
import math
from copy import deepcopy
from typing import Generator, Sequence, Collection
from unittest.mock import Mock, patch, AsyncMock

import pytest
from faker import Faker
from pytest_mock import MockerFixture

from musify.models.api import RemoteAPI
from musify.models.api.playlist import PlaylistReadWriteEndpoints
from musify.models.collection import CollectionModel
from musify.models.collection.playlist import RemoteMutablePlaylist
from musify.models.item.track import Track, RemoteTrack
from musify.processors_new.check import Checker
from musify.processors_new.formatter import CollectionFormatter
from tests.conftest import LogCapturer
from tests.libraries.remote.core.processors.utils import patch_input
from tests.models.api.utils import MockUrlCursor
from tests.processors_new.utils import assert_help_text, MockCollection
from tests.utils import SimpleURI


class TestPausePages:
    @pytest.fixture
    def model(self, api: RemoteAPI) -> Checker:
        return Checker(api=api)

    @pytest.fixture(autouse=True)
    def playlists(self, model: Checker, playlists: list[RemoteMutablePlaylist]) -> list[RemoteMutablePlaylist]:
        model._playlists = {pl.uri: pl for pl in playlists}
        model._playlists_initial = {pl.uri: deepcopy(pl) for pl in playlists}
        return playlists

    @pytest.fixture
    def collections(
            self, model: Checker, playlists: list[RemoteMutablePlaylist], tracks: list[Track], faker: Faker
    ) -> list[CollectionModel]:
        collections = [
            MockCollection(
                name=pl.name,
                cursor=MockUrlCursor(url=faker.url()),
                all_items=faker.random_elements(tracks),
                uri=SimpleURI.create_random(MockCollection.type),
            )
            for pl in playlists
        ]

        model._collections = {pl.uri: coll for pl, coll in zip(playlists, collections)}
        return collections

    @pytest.fixture
    def pages(self, model: Checker, collections: list[CollectionModel]) -> int:
        total = len(collections)
        model.interval = total // 4
        return math.ceil(total / model.interval)

    @pytest.fixture
    def mock_get_playlist_items(self, tracks: list[RemoteTrack], faker: Faker) -> Generator[Mock, None, None]:
        def _random_tracks(*_, **__) -> Sequence[RemoteTrack]:
            return faker.random_elements(tracks)

        with patch.object(
                PlaylistReadWriteEndpoints, "get_all", side_effect=_random_tracks, new_callable=AsyncMock
        ) as mock_get_all:
            yield mock_get_all

    @pytest.fixture
    def mock_pause(self, model: Checker, mocker: MockerFixture) -> Mock:
        return mocker.spy(model, "_run_pause_page")

    @pytest.fixture
    def mock_playlist_links(self, model: Checker, mocker: MockerFixture) -> Mock:
        return mocker.spy(model, "_print_playlist_links")

    @pytest.fixture
    def mock_playlist_items(self, model: Checker, mocker: MockerFixture) -> Mock:
        return mocker.spy(model, "_print_playlist_items")

    @pytest.fixture
    def mock_teardown_playlists(self, model: Checker, mocker: MockerFixture) -> Mock:
        return mocker.spy(model, "_teardown_playlists")

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
            log_capturer: LogCapturer,
    ):
        inputs = list(inputs)

        if "q" in inputs:
            inputs = inputs[:inputs.index("q") + 1]
        if "s" in inputs:
            inputs = inputs[:inputs.index("s") + 1]

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

        assert_help_text(log_capturer, expected_help)

        # assert mock_match.call_count == expected_pages  # TODO: add once implemented

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
            log_capturer: LogCapturer
    ):
        inputs = [""] * pages + ["h"] + ["invalid_input"]  # add some other random inputs
        with (patch_input(iter(inputs)), log_capturer(loggers=model.logger)):
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
            log_capturer=log_capturer
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
            log_capturer: LogCapturer
    ):
        inputs = ["h", "h", "", "h", "", "h"] + [""] * pages
        with (patch_input(iter(inputs)), log_capturer(loggers=model.logger)):
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
            log_capturer=log_capturer
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
            log_capturer: LogCapturer
    ):
        inputs = ["", "h", "", "s"]
        with (patch_input(iter(inputs)), log_capturer(loggers=model.logger)):
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
            log_capturer=log_capturer
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
            log_capturer: LogCapturer
    ):
        inputs = ["", "h", "", "q"]
        with (patch_input(iter(inputs)), log_capturer(loggers=model.logger)):
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
            log_capturer=log_capturer
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
            log_capturer: LogCapturer,
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

        with (patch_input(iter(inputs)), log_capturer(loggers=model.logger)):
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
            log_capturer=log_capturer
        )

        # assert explicitly to be sure
        assert mock_playlist_links.call_count == 4
        assert mock_playlist_items.call_count == 2

    async def test_print_playlist_items_no_changes(
            self,
            model: Checker,
            playlist: RemoteMutablePlaylist,
            mock_get_playlist_items: Mock,
            mocker: MockerFixture,
            faker: Faker,
    ):
        mock_format = mocker.spy(CollectionFormatter, "format")
        mock_get_playlist_items.reset_mock(side_effect=True)
        mock_get_playlist_items.return_value = playlist.tracks

        await model._print_playlist_items(playlist)
        mock_format.assert_called_once_with(model.formatter, playlist, indices=True)

    async def test_print_playlist_items_with_changes(
            self,
            model: Checker,
            playlist: RemoteMutablePlaylist,
            tracks: list[RemoteTrack],
            mock_get_playlist_items: Mock,
            mocker: MockerFixture,
            faker: Faker,
    ):
        mock_format = mocker.spy(CollectionFormatter, "format")

        await model._print_playlist_items(playlist)
        assert mock_format.call_count == 2
