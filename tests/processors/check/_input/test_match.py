from collections.abc import Sequence

import pytest

from mytunes.core.api import RemoteAPI
from mytunes.core.properties.order import Position
from mytunes.core.properties.uri import HasMutableURI
from mytunes.processors.check._input.match import InputMatch
from mytunes.processors.check._input.page import InputPage
from tests.processors.check.testers import InputMatchTester


class TestInputMatch(InputMatchTester):
    @pytest.fixture
    def model(self, page: InputPage) -> InputMatch:
        return InputMatch(page=page)

    @pytest.fixture
    def page(
            self, position: Position, missing_items: Sequence[HasMutableURI], api: RemoteAPI, faker: Faker
    ) -> InputPage:
        name = faker.name()
        return InputPage(name=name, position=position, api=api, items=missing_items)
