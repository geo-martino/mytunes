import math
from collections.abc import Generator
from unittest.mock import Mock, patch

import pytest
from faker import Faker
from mytunes._models.api import RemoteAPI
from mytunes._models.item.track import RemoteTrack
from mytunes._models.properties.name import HasName
from mytunes.processors._flow import QuitImmediately, SkipPage
from mytunes.processors.check import Checker
from mytunes.processors.check._match.inputs import InputMatch
from mytunes.processors.check._match.playlist import PlaylistMatch
from mytunes.processors.check._page import CheckerPage
from mytunes.processors.check.result import CheckResult
from pytest_mock import MockerFixture
from tests.processors.utils import MockCollection
from tests.testers import BaseModelTester


class TestChecker(BaseModelTester):
    @pytest.fixture
    def model(self, api: RemoteAPI) -> Checker:
        return Checker(api=api)

    @pytest.fixture
    def mock_check_page(self, model: Checker, mocker: MockerFixture) -> Mock:
        return mocker.spy(Checker, "_check_page")

    @pytest.fixture
    def mock_match_page(self, model: Checker, mocker: MockerFixture) -> Mock:
        return mocker.spy(Checker, "_match_page")

    @pytest.fixture(autouse=True)
    def mock_pause(self) -> Generator[Mock, None, None]:
        with patch.object(CheckerPage, "pause") as mock_pause:
            yield mock_pause

    @pytest.fixture(autouse=True)
    def mock_match_playlist(self, mocker: MockerFixture) -> Mock:
        return mocker.spy(PlaylistMatch, "match")

    @pytest.fixture(autouse=True)
    def mock_match_input(self, mocker: MockerFixture) -> Mock:
        return mocker.spy(InputMatch, "match")

    async def test_check_skips_on_empty_collections(
            self,
            model: Checker,
            collections: list[MockCollection],
            mock_check_page: Mock,
            mock_match_page: Mock,
            faker: Faker,
    ):
        for collection in collections:
            collection.all_items.clear()

        assert not await model.check(collections)
        mock_check_page.assert_not_called()
        mock_match_page.assert_not_called()

    async def test_check_skips_on_invalid_collections(
            self,
            model: Checker,
            collections: list[MockCollection],
            mock_check_page: Mock,
            mock_match_page: Mock,
            faker: Faker,
    ):
        for collection in collections:
            collection.all_items = [HasName(name=faker.name()) for _ in range(faker.random_int(1, 10))]

        assert not await model.check(collections)
        mock_check_page.assert_not_called()
        mock_match_page.assert_not_called()

    async def test_check_runs_all_collections(
            self,
            model: Checker,
            collections: list[MockCollection],
            mock_check_page: Mock,
            mock_match_page: Mock,
            mock_pause: Mock,
            mock_match_playlist: Mock,
            mock_match_input: Mock,
            faker: Faker,
    ):
        model.interval = len(collections) // 4
        expected_pages = math.ceil(len(collections) / model.interval)

        results = await model.check(collections)

        assert results.keys() == {collection.name for collection in collections}

        assert mock_check_page.call_count == expected_pages
        assert mock_match_page.call_count == len(collections)
        assert mock_pause.call_count == expected_pages
        assert mock_match_playlist.call_count == len(collections)
        assert mock_match_input.call_count == sum(bool(result.skipped) for result in results.values())

    async def test_check_only_runs_input_match_if_needed(
            self,
            model: Checker,
            collections: list[MockCollection],
            tracks: list[RemoteTrack],
            mock_match_input: Mock,
            faker: Faker,
    ):
        # force playlist matches to always return valid result
        def _return_valid_playlist_match() -> CheckResult:
            return CheckResult(
                changed=faker.random_elements(tracks, unique=True),
                unchanged=faker.random_elements(tracks, unique=True)
            )

        with patch.object(PlaylistMatch, "match", side_effect=_return_valid_playlist_match) as mock_match_playlist:
            await model.check(collections)

            assert mock_match_playlist.call_count == len(collections)
            mock_match_input.assert_not_called()

    async def test_check_skips_match(
            self,
            model: Checker,
            collections: list[MockCollection],
            mock_match_playlist: Mock,
            mock_match_input: Mock,
            faker: Faker,
    ):
        with patch.object(CheckerPage, "pause", side_effect=SkipPage):
            await model.check(collections)

            mock_match_playlist.assert_not_called()
            mock_match_input.assert_not_called()

    async def test_check_quits_match(
            self,
            model: Checker,
            collections: list[MockCollection],
            mock_check_page: Mock,
            mock_match_page: Mock,
            mock_match_playlist: Mock,
            mock_match_input: Mock,
            faker: Faker,
    ):
        exception = faker.random_element((KeyboardInterrupt, QuitImmediately))

        with patch.object(CheckerPage, "pause", side_effect=exception) as mock_pause:
            await model.check(collections)

            mock_check_page.assert_called_once()
            mock_match_page.assert_not_called()
            mock_pause.assert_called_once()
            mock_match_playlist.assert_not_called()
            mock_match_input.assert_not_called()
