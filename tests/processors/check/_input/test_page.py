from collections.abc import Sequence

import pytest
from faker import Faker

from mytunes.core.api import RemoteAPI
from mytunes.core.properties.order import Position
from mytunes.core.properties.uri import HasMutableURI
from mytunes.processors.check._input.page import InputPage
from tests.testers import BaseModelTester
from tests.utils import patch_input


class TestInputPage(BaseModelTester):
    @pytest.fixture
    def model(
            self, position: Position, missing_items: Sequence[HasMutableURI], api: RemoteAPI, faker: Faker
    ) -> InputPage:
        name = faker.name()
        return InputPage(name=name, position=position, api=api, items=missing_items)

    async def test_pause(self, model: InputPage, faker: Faker):
        with patch_input(["y"]):
            assert await model.pause()
        with patch_input([faker.sentence(), "yes"]):
            assert await model.pause()

        with patch_input(["n"]):
            assert not await model.pause()
        with patch_input([faker.sentence(), "no"]):
            assert not await model.pause()
