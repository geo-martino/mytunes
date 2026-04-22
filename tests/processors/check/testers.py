from pydantic import TypeAdapter
from pytest_mock import MockerFixture

from testers import BaseModelTester

from abc import ABCMeta
from collections.abc import Collection, Sequence, Generator
from copy import deepcopy
from unittest.mock import patch, MagicMock, PropertyMock, Mock

import pytest
from faker import Faker

from mytunes._base.resource import ResourceModel
from mytunes.core._collection import CollectionModel
from mytunes.core._collection.playlist import RemoteMutablePlaylist
from mytunes.core.api import RemoteAPI
from mytunes.core.properties.order import Position
from mytunes.core.properties.uri import HasURI, HasMutableURI, URI
from mytunes.processors._flow import QuitImmediately
from mytunes.processors.check._match import BaseMatch, BaseInputMatch
from mytunes.processors.check._page import CheckerPage
from mytunes.processors.match import Matcher
from mytunes.result import LogFormatter
from processors.check._playlist.utils import HasNameAndImmutableURI, HasNameAndMutableURI
from processors.utils import MockCollection
from remote import SimpleURI
from tests.testers import BaseModelTester
from utils import patch_input


class InputMatchTester(BaseModelTester, metaclass=ABCMeta):
    @pytest.fixture(autouse=True)
    def mock_uri_adapter(self) -> Generator[Mock]:
        adapter = TypeAdapter(SimpleURI)
        with patch.object(URI, "get_adapter_for_source", return_value=adapter) as mock_adapter:
            yield mock_adapter

    @pytest.fixture
    def mock_match_item_with_input(self, model: BaseInputMatch, mocker: MockerFixture) -> Mock:
        return mocker.spy(model, '_match_item_with_input')

    @pytest.fixture
    def mock_compare_uri_changes(self, model: BaseInputMatch, mocker: MockerFixture) -> Mock:
        return mocker.spy(model, '_compare_uri_changes')

    ###########################################################################
    ## Match
    ###########################################################################
    @staticmethod
    async def test_match_skips_on_no_missing_items(
            model: BaseInputMatch,
            mutable_items: list[HasNameAndMutableURI],
            mock_match_item_with_input: Mock,
            mock_compare_uri_changes: Mock,
    ):
        result = await model.match(mutable_items)

        assert not result.changed
        assert not result.unchanged
        assert not result.unavailable
        assert not result.skipped

        mock_match_item_with_input.assert_not_called()
        mock_compare_uri_changes.assert_not_called()

    @staticmethod
    async def test_match_skips(
            model: BaseInputMatch,
            missing_items: list[HasNameAndMutableURI],
            mock_match_item_with_input: Mock,
            mock_compare_uri_changes: Mock,
    ):
        kind = missing_items[0].type
        inputs = [
            SimpleURI.create_random(kind),
            "h",
            SimpleURI.create_random(kind),
            "s",
        ]

        with patch_input(iter(inputs)):
            result = await model.match(missing_items)

        assert len(result.changed) == 2
        assert not result.unchanged
        assert not result.unavailable
        assert len(result.skipped) == len(missing_items) - len(result.changed)

        assert mock_match_item_with_input.call_count == 3  # quits early
        mock_compare_uri_changes.assert_called_once()

    @staticmethod
    async def test_match_quits(
            model: BaseInputMatch,
            missing_items: list[HasNameAndMutableURI],
            mock_match_item_with_input: Mock,
            mock_compare_uri_changes: Mock,
    ):
        kind = missing_items[0].type
        inputs = [
            SimpleURI.create_random(kind),
            "h",
            SimpleURI.create_random(kind),
            "q",
        ]

        with patch_input(iter(inputs)), pytest.raises(QuitImmediately):
            await model.match(missing_items)

        assert mock_match_item_with_input.call_count == 3  # quits early
        mock_compare_uri_changes.assert_not_called()  # doesn't produce a result

    @staticmethod
    async def test_match_assigns_uris(
            model: BaseInputMatch,
            missing_items: list[HasNameAndMutableURI],
            mock_match_item_with_input: Mock,
            mock_compare_uri_changes: Mock,
    ):
        uris = [SimpleURI.create_random(kind=item.type) for item in missing_items]
        with patch_input(iter(uris)):
            result = await model.match(missing_items)

        assert sorted(result.changed) == sorted(missing_items)
        assert not result.unchanged
        assert not result.unavailable
        assert not result.skipped

        assert mock_match_item_with_input.call_count == len(missing_items)
        mock_compare_uri_changes.assert_called_once()

    @staticmethod
    async def test_match_complex_assignment(
            model: BaseInputMatch,
            missing_items: list[HasNameAndMutableURI],
            mock_match_item_with_input: Mock,
            mock_compare_uri_changes: Mock,
    ):
        kind = missing_items[0].type
        inputs = [
            "h",
            "invalid_input",
            "n",
            SimpleURI.create_random(kind),
            "h",
            "u",
            SimpleURI.create_unavailable(kind),
            "n",
            "h",
            "invalid_input",
            "n",
            SimpleURI.create_unavailable(kind),
            "invalid_input",
            SimpleURI.create_random(kind),
            "s",
        ]

        with patch_input(iter(inputs)):
            result = await model.match(missing_items)

        assert len(result.changed) == 2
        assert not result.unchanged
        assert len(result.unavailable) == 3
        assert len(result.skipped) == len(missing_items) - len(result.changed) - len(result.unavailable)

        assert mock_match_item_with_input.call_count == 9
        mock_compare_uri_changes.assert_called_once()
