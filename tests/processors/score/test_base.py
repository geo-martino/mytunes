from unittest.mock import patch, Mock, MagicMock

import pytest
from pydantic import InstanceOf

from mytunes._models.properties.name import HasName
from mytunes.processors.score import Scorer
from tests.testers import BaseModelTester


class TestScorer(BaseModelTester):
    @pytest.fixture
    @patch.multiple(
        Scorer,
        __abstractmethods__=set(),
        _calculate_score=MagicMock(),
    )
    def model(self) -> Scorer:
        return Scorer[InstanceOf[Mock]](type="test", cleaner=Mock())

    def test_score(self, model: Scorer):
        model.cleaner.clean = Mock(side_effect=lambda x: x.name)

        item = HasName(name="test item")
        other = HasName(name="other item")

        with patch.object(model, "_calculate_score", return_value=1) as mock_calculate_score:  # abstractmethod
            model.score(item=item, other=other)
            mock_calculate_score.assert_called_once_with(item.name, other.name)

        model.cleaner.clean.assert_any_call(item)
        model.cleaner.clean.assert_any_call(other)

