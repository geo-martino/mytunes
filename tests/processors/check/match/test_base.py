from unittest.mock import Mock, patch

import pytest

from musify.models import ResourceModel
from musify.models.collection import CollectionModel
from musify.models.properties.uri import HasURI, HasImmutableURI
from musify.processors.check._match._base import CheckerMatch
from musify.processors.check._page import CheckerPage
from musify.processors.match import Matcher
from tests.models.testers import BaseModelTester


class TestCheckerMatch(BaseModelTester):
    @pytest.fixture
    @patch.multiple(
        CheckerMatch,
        __abstractmethods__=set(),
        match=Mock(),
    )
    def model(self, page: CheckerPage, matcher: Matcher) -> CheckerMatch:
        return CheckerMatch(page=page, matcher=matcher)

    def test_get_valid_items(
            self,
            model: CheckerMatch,
            collection: CollectionModel,
            available_items: list[HasURI],
            mutable_items: list[HasURI],
    ):
        result = model.get_valid_items(collection.items)
        assert result == available_items + mutable_items

    def test_get_missing_items(
            self,
            model: CheckerMatch,
            collection: CollectionModel,
            missing_items: list[HasURI],
    ):
        result = model.get_missing_items(collection.items)
        assert result == missing_items

    def test_get_unavailable_items(
            self,
            model: CheckerMatch,
            collection: CollectionModel,
            unavailable_items: list[HasURI],
    ):
        result = model.get_unavailable_items(collection.items)
        assert result == unavailable_items

    def test_get_invalid_items(
            self,
            model: CheckerMatch,
            collection: CollectionModel,
            available_items: list[HasImmutableURI],
            unavailable_items: list[HasImmutableURI],
            invalid_items: list[ResourceModel],
    ):
        result = model.get_invalid_items(collection.items)
        assert result == available_items + unavailable_items + invalid_items
