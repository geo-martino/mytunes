from collections.abc import Collection
from unittest.mock import patch, MagicMock, PropertyMock

import pytest
from faker import Faker

from mytunes._base.resource import ResourceModel
from mytunes.core._collection import CollectionModel
from mytunes.core._collection.playlist import RemoteMutablePlaylist
from mytunes.core.api import RemoteAPI
from mytunes.core.properties.order import Position
from mytunes.core.properties.uri import HasURI, HasMutableURI
from mytunes.processors.check._match import CheckerMatch
from mytunes.processors.check._page import CollectionsPage
from mytunes.processors.match import Matcher
from processors.utils import MockCollection
from tests.testers import NoUniqueKeyTester


class TestCheckerMatch(NoUniqueKeyTester):
    @pytest.fixture
    @patch.multiple(
        CheckerMatch,
        __abstractmethods__=set(),
        match=MagicMock(),
    )
    def model(self, page: CollectionsPage) -> CheckerMatch:
        # noinspection PyAbstractClass
        return CheckerMatch(page=page)

    # noinspection PyAbstractClass
    @pytest.fixture
    @patch.multiple(
        CollectionsPage,
        __abstractmethods__=set(),
        _options=PropertyMock(),
        pause=MagicMock(),
    )
    def page(self, position: Position, collections: Collection[CollectionModel], api: RemoteAPI) -> CollectionsPage:
        return CollectionsPage(position=position, api=api, collections=collections)

    @pytest.fixture
    def items(
        self,
        available_items: list[HasURI],
        unavailable_items: list[HasURI],
        missing_items: list[HasURI],
        invalid_items: list[ResourceModel],
        mutable_items: list[HasMutableURI],
    ) -> list[ResourceModel]:
        return available_items + unavailable_items + missing_items + invalid_items + mutable_items

    def test_getters(
            self,
            model: CheckerMatch,
            items: list[ResourceModel],
            available_items: list[HasURI],
            mutable_items: list[HasURI],
            missing_items: list[HasURI],
            unavailable_items: list[HasURI],
    ):
        assert model.get_valid_items(items) == mutable_items
        assert model.get_missing_items(items) == missing_items
        assert model.get_unavailable_items(items) == unavailable_items
