from unittest.mock import patch, MagicMock

import pytest

from musify._models.collection import CollectionModel
from musify._models.collection.playlist import RemoteMutablePlaylist
from musify._models.properties.uri import HasURI
from musify.processors.check._match._base import CheckerMatch
from musify.processors.check._page import CheckerPage
from musify.processors.match import Matcher
from tests.testers import UniqueKeyTester


class TestCheckerMatch(UniqueKeyTester):
    @pytest.fixture
    @patch.multiple(
        CheckerMatch,
        __abstractmethods__=set(),
        match=MagicMock(),
    )
    def model(
            self,
            page: CheckerPage,
            playlist: RemoteMutablePlaylist,
            collection: CollectionModel,
            matcher: Matcher,
    ) -> CheckerMatch:
        return CheckerMatch(page=page, items=list(collection.items), uri=playlist.uri, matcher=matcher)

    def test_properties(
            self,
            model: CheckerMatch,
            available_items: list[HasURI],
            mutable_items: list[HasURI],
            missing_items: list[HasURI],
            unavailable_items: list[HasURI],
    ):
        assert model.valid_items == mutable_items
        assert model.missing_items == missing_items
        assert model.unavailable_items == unavailable_items
