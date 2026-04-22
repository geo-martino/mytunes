import math
from collections.abc import Generator, Collection
from unittest.mock import Mock, patch, AsyncMock

import pytest
from faker import Faker
from pytest_mock import MockerFixture

from mytunes.core._collection.playlist import RemoteMutablePlaylist
from mytunes.core._item.track import RemoteTrack
from mytunes.core.api import RemoteAPI
from mytunes.core.properties.name import HasName
from mytunes.processors._flow import QuitImmediately, SkipPage
from mytunes.processors.check import Checker
from mytunes.processors.check._playlist.match import PlaylistMatch, InputMatch
from mytunes.processors.check._playlist.page import PlaylistsPage
from mytunes.processors.check.result import CheckResult
from tests.processors.utils import MockCollection
from tests.testers import BaseModelTester


class TestChecker(BaseModelTester):
    @pytest.fixture
    def model(self, api: RemoteAPI) -> Checker:
        return Checker(api=api)

    @pytest.fixture
    def mock_check_playlist_page(self, model: Checker, mocker: MockerFixture) -> Mock:
        return mocker.spy(Checker, "_check_playlist_page")

    @pytest.fixture
    def mock_match_playlist_page(self, model: Checker, mocker: MockerFixture) -> Mock:
        return mocker.spy(Checker, "_match_playlist")

    @pytest.fixture(autouse=True)
    def mock_pause(self) -> Generator[Mock]:
        with patch.object(PlaylistsPage, "pause") as mock_pause:
            yield mock_pause

    @pytest.fixture(autouse=True)
    def mock_playlist_match(self, mocker: MockerFixture) -> Mock:
        return mocker.spy(PlaylistMatch, "match")

    @pytest.fixture(autouse=True)
    def mock_input_match(self, mocker: MockerFixture) -> Mock:
        return mocker.spy(InputMatch, "match")

    async def test_check_skips_on_empty_collections(
            self,
            model: Checker,
            collections: list[MockCollection],
            mock_check_playlist_page: Mock,
            mock_match_playlist_page: Mock,
            faker: Faker,
    ):
        for collection in collections:
            collection.all_items.clear()

        assert not await model.check_collections_on_playlists(collections)
        mock_check_playlist_page.assert_not_called()
        mock_match_playlist_page.assert_not_called()

    async def test_check_collections_on_playlists_skips_on_invalid_collections(
            self,
            model: Checker,
            collections: list[MockCollection],
            mock_check_playlist_page: Mock,
            mock_match_playlist_page: Mock,
            faker: Faker,
    ):
        for collection in collections:
            collection.all_items = [HasName(name=faker.name()) for _ in range(faker.random_int(1, 10))]

        assert not await model.check_collections_on_playlists(collections)
        mock_check_playlist_page.assert_not_called()
        mock_match_playlist_page.assert_not_called()

    async def test_check_collections_on_playlists_runs_all_collections(
            self,
            model: Checker,
            collections: list[MockCollection],
            mock_check_playlist_page: Mock,
            mock_match_playlist_page: Mock,
            mock_pause: Mock,
            mock_playlist_match: Mock,
            mock_input_match: Mock,
    ):
        model.interval = len(collections) // 4
        expected_pages = math.ceil(len(collections) / model.interval)

        results = await model.check_collections_on_playlists(collections)

        assert len(results) == len(collections)

        assert mock_check_playlist_page.call_count == expected_pages
        assert mock_match_playlist_page.call_count == len(collections)
        assert mock_pause.call_count == expected_pages
        assert mock_playlist_match.call_count == len(collections)
        assert mock_input_match.call_count == sum(bool(result.skipped) for _, result in results)

    async def test_check_collections_on_playlists_only_runs_input_match_if_needed(
            self,
            model: Checker,
            collections: list[MockCollection],
            tracks: list[RemoteTrack],
            mock_playlist_match: Mock,
            mock_input_match: Mock,
            faker: Faker,
    ):
        # force playlist matches to always return valid result
        def _return_valid_playlist_match[T](items: Collection[T]) -> CheckResult[T]:
            return CheckResult(
                changed=faker.random_elements(items, unique=True),
                unchanged=faker.random_elements(items, unique=True),
            )

        with patch.object(PlaylistMatch, "match", side_effect=_return_valid_playlist_match):
            await model.check_collections_on_playlists(collections)

        await model.check_collections_on_playlists(collections)

        assert mock_playlist_match.call_count == len(collections)
        mock_input_match.assert_not_called()

    async def test_check_collections_on_playlists_skips_match(
            self,
            model: Checker,
            collections: list[MockCollection],
            mock_playlist_match: Mock,
            mock_input_match: Mock,
            faker: Faker,
    ):
        with patch.object(PlaylistsPage, "pause", side_effect=SkipPage):
            await model.check_collections_on_playlists(collections)

            mock_playlist_match.assert_not_called()
            mock_input_match.assert_not_called()

    async def test_check_collections_on_playlists_quits_match(
            self,
            model: Checker,
            collections: list[MockCollection],
            mock_check_playlist_page: Mock,
            mock_match_playlist_page: Mock,
            mock_playlist_match: Mock,
            mock_input_match: Mock,
            faker: Faker,
    ):
        exception = faker.random_element((KeyboardInterrupt, QuitImmediately))

        with patch.object(PlaylistsPage, "pause", side_effect=exception) as mock_pause:
            await model.check_collections_on_playlists(collections)

            mock_check_playlist_page.assert_called_once()
            mock_match_playlist_page.assert_not_called()
            mock_pause.assert_called_once()
            mock_playlist_match.assert_not_called()
            mock_input_match.assert_not_called()
