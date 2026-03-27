import pytest

from musify.models.api import RemoteAPI
from musify.processors_new.check import Checker
from tests.models.testers import BaseModelTester


class TestChecker(BaseModelTester):
    @pytest.fixture
    def model(self, api: RemoteAPI) -> Checker:
        return Checker(api=api)
