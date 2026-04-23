import itertools
import math
from abc import abstractmethod
from collections.abc import Generator, Collection, Sequence
from unittest.mock import Mock, patch, AsyncMock

import pytest
from faker import Faker
from pytest_mock import MockerFixture

from mytunes.core._collection import CollectionModel
from mytunes.core._collection.playlist import RemoteMutablePlaylist
from mytunes.core._item.track import RemoteTrack
from mytunes.core.api import RemoteAPI
from mytunes.core.api.playlist import PlaylistReadWriteEndpoints
from mytunes.core.properties.name import HasName
from mytunes.processors._flow import QuitImmediately, SkipPage
from mytunes.processors.check._check import Checker, ItemChecker, CollectionChecker
from mytunes.processors.check._input.match import InputMatch as SimpleInputMatch
from mytunes.processors.check._input.page import InputPage
from mytunes.processors.check._playlist.match import SyncMatch, InputMatch as PlaylistInputMatch
from mytunes.processors.check._playlist.page import PlaylistsPage
from mytunes.processors.check.result import CheckResult
from tests.processors.utils import MockCollection
from tests.testers import BaseModelTester
from utils import patch_input


class CheckerTester(BaseModelTester):

    @abstractmethod
    def mock_pause(self) -> Generator[Mock]:
        raise NotImplementedError

    @pytest.fixture
    def mock_check_page(self, model: Checker, mocker: MockerFixture) -> Mock:
        return mocker.spy(model, "_check_page")

    @pytest.fixture
    def mock_match_page(self, model: Checker, mocker: MockerFixture) -> Mock:
        return mocker.spy(model, "_match_page")


class TestItemChecker(CheckerTester):
    @pytest.fixture
    def model(self, api: RemoteAPI) -> ItemChecker:
        return ItemChecker(api=api)

    @pytest.fixture(autouse=True)
    def mock_pause(self) -> Generator[Mock]:
        with patch.object(InputPage, "pause") as mock_pause:
            yield mock_pause

    @pytest.fixture(autouse=True)
    def mock_input_match(self, mocker: MockerFixture) -> Mock:
        return mocker.spy(SimpleInputMatch, "match")

    async def test_check_runs_all_with_match(
            self,
            model: ItemChecker,
            tracks: list[RemoteTrack],
            mock_check_page: Mock,
            mock_match_page: Mock,
            mock_pause: Mock,
            mock_input_match: Mock,
    ):
        mock_pause.return_value = False

        result = await model.check(tracks)

        assert isinstance(result, CheckResult)

        mock_check_page.assert_called_once()
        mock_pause.assert_called_once()
        mock_match_page.assert_called_once()
        mock_input_match.assert_called_once()

    async def test_check_runs_all_skip_match(
            self,
            model: ItemChecker,
            tracks: list[RemoteTrack],
            mock_check_page: Mock,
            mock_match_page: Mock,
            mock_pause: Mock,
            mock_input_match: Mock,
    ):
        mock_pause.return_value = True
        result = await model.check(tracks)

        assert isinstance(result, CheckResult)

        mock_check_page.assert_called_once()
        mock_pause.assert_called_once()
        mock_match_page.assert_not_called()
        mock_input_match.assert_not_called()

    async def test_check_skips_invalid(
            self,
            model: ItemChecker,
            collections: list[Collection],
            mock_check_page: Mock,
            mock_match_page: Mock,
            faker: Faker,
    ):
        # noinspection PyTypeChecker
        assert not await model.check(collections)

        mock_check_page.assert_not_called()
        mock_match_page.assert_not_called()

    async def test_check_skips_match(
            self,
            model: ItemChecker,
            tracks: list[RemoteTrack],
            mock_input_match: Mock,
            faker: Faker,
    ):
        with patch.object(InputPage, "pause", side_effect=SkipPage):
            await model.check(tracks)

        mock_input_match.assert_not_called()

    async def test_check_quits_match(
            self,
            model: ItemChecker,
            tracks: list[RemoteTrack],
            mock_check_page: Mock,
            mock_match_page: Mock,
            mock_pause: Mock,
            mock_input_match: Mock,
            faker: Faker,
    ):
        mock_pause.side_effect = QuitImmediately

        await model.check(tracks)

        mock_check_page.assert_called_once()
        mock_pause.assert_called_once()
        mock_match_page.assert_not_called()
        mock_input_match.assert_not_called()


class TestCollectionChecker(CheckerTester):
    @pytest.fixture
    def model(self, api: RemoteAPI) -> CollectionChecker:
        return CollectionChecker(api=api)

    @pytest.fixture
    def mock_pause(self) -> Generator[Mock]:
        with patch.object(PlaylistsPage, "pause") as mock_pause:
            yield mock_pause

    @pytest.fixture(autouse=True)
    def mock_sync_match(self, mocker: MockerFixture) -> Mock:
        return mocker.spy(SyncMatch, "match")

    @pytest.fixture(autouse=True)
    def mock_input_match(self, mocker: MockerFixture) -> Mock:
        return mocker.spy(PlaylistInputMatch, "match")

    async def test_check_skips_on_empty_collections(
            self,
            model: CollectionChecker,
            collections: list[MockCollection],
            mock_check_page: Mock,
            mock_match_page: Mock,
            faker: Faker,
    ):
        for collection in collections:
            collection.all_items.clear()

        assert not await model.check_on_playlists(collections)
        mock_check_page.assert_not_called()
        mock_match_page.assert_not_called()

    async def test_check_skips_on_invalid_collections(
            self,
            model: CollectionChecker,
            collections: list[MockCollection],
            mock_check_page: Mock,
            mock_match_page: Mock,
            faker: Faker,
    ):
        for collection in collections:
            collection.all_items = [HasName(name=faker.name()) for _ in range(faker.random_int(1, 10))]

        assert not await model.check_on_playlists(collections)
        mock_check_page.assert_not_called()
        mock_match_page.assert_not_called()

    async def test_check_runs_all(
            self,
            model: CollectionChecker,
            collections: list[MockCollection],
            mock_check_page: Mock,
            mock_match_page: Mock,
            mock_pause: Mock,
            mock_sync_match: Mock,
            mock_input_match: Mock,
    ):
        model.interval = len(collections) // 4
        expected_pages = math.ceil(len(collections) / model.interval)

        results = await model.check_on_playlists(collections)

        assert len(results) == len(collections)

        assert mock_check_page.call_count == expected_pages
        assert mock_match_page.call_count == len(collections)
        assert mock_pause.call_count == expected_pages
        assert mock_sync_match.call_count == len(collections)
        assert mock_input_match.call_count == sum(bool(result.skipped) for _, result in results)

    async def test_check_only_runs_input_match_if_needed(
            self,
            model: CollectionChecker,
            collections: list[MockCollection],
            tracks: list[RemoteTrack],
            mock_pause: Mock,
            mock_sync_match: Mock,
            mock_input_match: Mock,
            faker: Faker,
    ):
        # force playlist matches to always return valid result
        def _return_valid_sync_match[T](items: Collection[T]) -> CheckResult[T]:
            return CheckResult(
                name=faker.name(),
                changed=faker.random_elements(items, unique=True),
                unchanged=faker.random_elements(items, unique=True),
            )

        with patch.object(SyncMatch, "match", side_effect=_return_valid_sync_match):
            await model.check_on_playlists(collections)

        await model.check_on_playlists(collections)

        assert mock_sync_match.call_count == len(collections)
        mock_input_match.assert_not_called()

    async def test_check_skips_match(
            self,
            model: CollectionChecker,
            collections: list[MockCollection],
            mock_sync_match: Mock,
            mock_input_match: Mock,
            faker: Faker,
    ):
        with patch.object(PlaylistsPage, "pause", side_effect=SkipPage):
            await model.check_on_playlists(collections)

            mock_sync_match.assert_not_called()
            mock_input_match.assert_not_called()

    async def test_check_quits_match(
            self,
            model: CollectionChecker,
            collections: list[MockCollection],
            mock_check_page: Mock,
            mock_match_page: Mock,
            mock_sync_match: Mock,
            mock_input_match: Mock,
            faker: Faker,
    ):
        with patch.object(PlaylistsPage, "pause", side_effect=QuitImmediately) as mock_pause:
            await model.check_on_playlists(collections)

            mock_check_page.assert_called_once()
            mock_match_page.assert_not_called()
            mock_pause.assert_called_once()
            mock_sync_match.assert_not_called()
            mock_input_match.assert_not_called()

    ###########################################################################
    ## Pause pagination
    ###########################################################################
    @pytest.fixture
    def pages(self, model: CollectionChecker, collections: list[CollectionModel]) -> int:
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
    def mock_playlist_pause(self, mocker: MockerFixture) -> Mock:
        return mocker.spy(PlaylistsPage, "pause")

    @pytest.fixture
    def mock_playlist_links(self, mocker: MockerFixture) -> Mock:
        return mocker.spy(PlaylistsPage, "_print_playlist_links")

    @pytest.fixture
    def mock_playlist_items(self, mocker: MockerFixture) -> Mock:
        return mocker.spy(PlaylistsPage, "_print_playlist_items")

    @pytest.fixture
    def mock_teardown_playlists(self, mocker: MockerFixture) -> Mock:
        return mocker.spy(PlaylistsPage, "teardown_playlists")

    @staticmethod
    def assert_pause_calls(
            model: CollectionChecker,
            inputs: Sequence[str],
            pages: int,
            names: Collection[str],
            mock_playlist_pause: Mock,
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

        names = {name.casefold() for name in names}
        expected_playlist_items = sum(val.casefold() in names for val in inputs)
        expected_playlist_links = inputs.count("l")

        assert mock_playlist_pause.call_count == expected_pages
        assert mock_playlist_links.call_count == expected_playlist_links
        assert mock_playlist_items.call_count == expected_playlist_items
        assert mock_teardown_playlists.call_count == expected_pages

    async def test_pages(
            self,
            model: CollectionChecker,
            collections: list[MockCollection],
            pages: int,
            mock_playlist_pause: Mock,
            mock_playlist_links: Mock,
            mock_playlist_items: Mock,
            mock_teardown_playlists: Mock,
    ):
        inputs = [""] * pages + ["h"] + ["invalid_input"]  # add some other random inputs
        with patch_input(inputs):
            await model.check_on_playlists(collections)

        self.assert_pause_calls(
            model,
            inputs=inputs,
            pages=pages,
            names={coll.name for coll in collections},
            mock_playlist_pause=mock_playlist_pause,
            mock_playlist_links=mock_playlist_links,
            mock_playlist_items=mock_playlist_items,
            mock_teardown_playlists=mock_teardown_playlists,
        )

    async def test_pause_prints_help(
            self,
            model: CollectionChecker,
            collections: list[MockCollection],
            pages: int,
            mock_playlist_pause: Mock,
            mock_playlist_links: Mock,
            mock_playlist_items: Mock,
            mock_teardown_playlists: Mock,
    ):
        inputs = ["h", "h", "", "h", "", "h"] + [""] * pages
        with patch_input(inputs):
            await model.check_on_playlists(collections)

        self.assert_pause_calls(
            model,
            inputs=inputs,
            pages=pages,
            names={coll.name for coll in collections},
            mock_playlist_pause=mock_playlist_pause,
            mock_playlist_links=mock_playlist_links,
            mock_playlist_items=mock_playlist_items,
            mock_teardown_playlists=mock_teardown_playlists,
        )

    async def test_pause_skips(
            self,
            model: CollectionChecker,
            collections: list[MockCollection],
            pages: int,
            mock_playlist_pause: Mock,
            mock_playlist_links: Mock,
            mock_playlist_items: Mock,
            mock_teardown_playlists: Mock,
    ):
        inputs = ["", "h", "", "s", "h"] + [""] * pages
        with patch_input(inputs):
            await model.check_on_playlists(collections)

        self.assert_pause_calls(
            model,
            inputs=inputs,
            pages=pages,
            names={coll.name for coll in collections},
            mock_playlist_pause=mock_playlist_pause,
            mock_playlist_links=mock_playlist_links,
            mock_playlist_items=mock_playlist_items,
            mock_teardown_playlists=mock_teardown_playlists,
        )

    async def test_pause_quits(
            self,
            model: CollectionChecker,
            collections: list[MockCollection],
            pages: int,
            mock_playlist_pause: Mock,
            mock_playlist_links: Mock,
            mock_playlist_items: Mock,
            mock_teardown_playlists: Mock,
    ):
        inputs = ["", "h", "", "q"]
        with patch_input(inputs):
            await model.check_on_playlists(collections)

        self.assert_pause_calls(
            model,
            inputs=inputs,
            pages=pages,
            names={coll.name for coll in collections},
            mock_playlist_pause=mock_playlist_pause,
            mock_playlist_links=mock_playlist_links,
            mock_playlist_items=mock_playlist_items,
            mock_teardown_playlists=mock_teardown_playlists,
        )

    async def test_pause_print_playlist(
            self,
            model: CollectionChecker,
            collections: list[MockCollection],
            playlists: list[RemoteMutablePlaylist],
            pages: int,
            mock_get_playlist_items: Mock,
            mock_playlist_pause: Mock,
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

        with patch_input(inputs):
            await model.check_on_playlists(collections)

        self.assert_pause_calls(
            model,
            inputs=inputs,
            pages=pages,
            names={coll.name for coll in collections},
            mock_playlist_pause=mock_playlist_pause,
            mock_playlist_links=mock_playlist_links,
            mock_playlist_items=mock_playlist_items,
            mock_teardown_playlists=mock_teardown_playlists,
        )

        # assert explicitly to be sure
        assert mock_playlist_links.call_count == 4
        assert mock_playlist_items.call_count == 2
