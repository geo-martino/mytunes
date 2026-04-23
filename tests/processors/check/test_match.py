from collections.abc import Sequence
from copy import deepcopy
from unittest.mock import patch, MagicMock, PropertyMock

import pytest
from faker import Faker

from mytunes._base.resource import ResourceModel
from mytunes.core._collection import CollectionModel
from mytunes.core.api import RemoteAPI
from mytunes.core.properties.order import Position
from mytunes.core.properties.uri import HasURI, HasMutableURI
from mytunes.processors.check._match import BaseMatch, BaseInputMatch
from mytunes.processors.check._page import CheckerPage
from mytunes.result import LogFormatter
from processors.check._playlist.utils import HasNameAndImmutableURI, HasNameAndMutableURI
from tests.remote import SimpleURI, URI_TYPES
from tests.testers import BaseModelTester


# noinspection PyAbstractClass
@pytest.fixture
@patch.multiple(
    CheckerPage,
    __abstractmethods__=set(),
    _options=PropertyMock(),
    pause=MagicMock(),
)
def page(position: Position, collections: Sequence[CollectionModel], api: RemoteAPI) -> CheckerPage:
    return CheckerPage(position=position, api=api, items=collections)


class TestBaseMatch(BaseModelTester):
    @pytest.fixture
    @patch.multiple(
        BaseMatch,
        __abstractmethods__=set(),
        name=PropertyMock(),
        match=MagicMock(),
    )
    def model(self, page: CheckerPage) -> BaseMatch:
        # noinspection PyAbstractClass
        return BaseMatch(page=page)

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
            model: BaseMatch,
            items: list[ResourceModel],
            available_items: list[HasURI],
            mutable_items: list[HasURI],
            missing_items: list[HasURI],
            unavailable_items: list[HasURI],
    ):
        assert model.get_valid_items(items) == mutable_items
        assert model.get_missing_items(items) == missing_items
        assert model.get_unavailable_items(items) == unavailable_items


class TestBaseInputMatch(BaseModelTester):
    @pytest.fixture
    @patch.multiple(
        BaseInputMatch,
        __abstractmethods__=set(),
        name=PropertyMock(),
        _match_item_with_input=MagicMock(),
    )
    def model(self, page: CheckerPage) -> BaseInputMatch:
        # noinspection PyAbstractClass
        return BaseInputMatch(page=page)

    @pytest.fixture
    def item(self, missing_items: list[HasNameAndMutableURI], faker: Faker) -> HasNameAndMutableURI:
        return faker.random_element(missing_items)

    ###########################################################################
    ## Utilities
    ###########################################################################
    def test_configure_formatter_for_items(
            self, model: BaseInputMatch, available_items: list[HasNameAndImmutableURI], faker: Faker
    ):
        width = max(len(item.name) for item in available_items)
        BaseInputMatch.input_formatter = LogFormatter(
            width=faker.random_int(),
            max_width=None,
        )

        formatter = model._configure_formatter_for_items(available_items)
        assert formatter.width == width

        width = max(width - faker.random_int(1, width), 3)
        BaseInputMatch.input_formatter = LogFormatter(
            width=faker.random_int(),
            max_width=width,
        )
        formatter = model._configure_formatter_for_items(available_items)
        assert formatter.width == width

    ###########################################################################
    ## Comparers
    ###########################################################################
    def test_compare_uri_changes(self, model: BaseInputMatch, mutable_items: list[HasNameAndMutableURI], faker: Faker):
        initial = mutable_items

        for change in faker.random_elements(initial, unique=True):
            if faker.boolean():
                change.uri = SimpleURI.create_unavailable(kind=change.type)
            else:
                del change.uri

        changed = []
        unchanged = []
        unavailable = []
        skipped = []

        changes = deepcopy(mutable_items)
        for change in changes:
            if change.has_uri is not None:
                unchanged.append(change)
                continue

            if faker.boolean():
                change.uri = SimpleURI.create_random(kind=change.type)
                changed.append(change)
                assert change.has_uri is True
            elif faker.boolean():
                change.uri = SimpleURI.create_unavailable(kind=change.type)
                unavailable.append(change)
                assert change.has_uri is False
            else:
                skipped.append(change)
                assert change.has_uri is None

        name = faker.name()
        with patch.object(BaseInputMatch, "name", return_value=name, new_callable=PropertyMock):
            result = model._compare_uri_changes(initial, changes)

        assert result.name == name
        assert sorted(result.changed) == sorted(changed)
        assert sorted(result.unchanged) == sorted(unchanged)
        assert sorted(result.unavailable) == sorted(unavailable)
        assert sorted(result.skipped) == sorted(skipped)

    def test_set_uri(self, model: BaseInputMatch, item: HasNameAndMutableURI, faker: Faker):
        uri = SimpleURI.create_random(kind=item.type)
        assert model._set_uri(item, str(uri))
        assert item.uri == uri
        assert item.has_uri is True

    def test_set_uri_skips_invalid_value(self, model: BaseInputMatch, item: HasNameAndMutableURI, faker: Faker):
        assert not model._set_uri(item, "not a uri")
        assert item.uri is None
        assert item.has_uri is None

    def test_set_uri_skips_invalid_type(self, model: BaseInputMatch, item: HasNameAndMutableURI, faker: Faker):
        other_type = faker.random_element(URI_TYPES)
        while other_type == item.type:
            other_type = faker.random_element(URI_TYPES)

        uri = SimpleURI.create_random(kind=other_type)

        assert not model._set_uri(item, str(uri))
        assert item.uri is None
        assert item.has_uri is None

    def test_set_unavailable_uri(self, model: BaseInputMatch, item: HasNameAndMutableURI, faker: Faker):
        assert model._set_unavailable_uri(item)
        assert item.uri is None
        assert item.has_uri is False

    def test_drop_uri(self, model: BaseInputMatch, item: HasNameAndMutableURI, faker: Faker):
        item.uri = SimpleURI.create_random(kind=item.type)

        assert model._drop_uri(item)
        assert item.uri is None
        assert item.has_uri is None
