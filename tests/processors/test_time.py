from datetime import timedelta

import pytest
from dateutil.relativedelta import relativedelta

from musify.processors.time import TimeMapper
from tests.testers import PrettyPrinterTester


class TestTimeMapper(PrettyPrinterTester):

    @pytest.fixture
    def obj(self) -> TimeMapper:
        return TimeMapper("hours")

    def test_time_mapper(self):
        assert TimeMapper("seconds")("55") == timedelta(seconds=55)
        assert TimeMapper("s")("55") == TimeMapper("s").map("55") == timedelta(seconds=55)

        assert TimeMapper("minutes")("36") == timedelta(minutes=36)
        assert TimeMapper("min")("36") == TimeMapper("min").map("36") == timedelta(minutes=36)

        assert TimeMapper("hours")("12") == timedelta(hours=12)
        assert TimeMapper("h")("12") == TimeMapper("h").map("12") == timedelta(hours=12)

        assert TimeMapper("days")("36") == timedelta(days=36)
        assert TimeMapper("d")("36") == TimeMapper("d").map("36") == timedelta(days=36)

        assert TimeMapper("weeks")("3") == timedelta(weeks=3)
        assert TimeMapper("w")("3") == TimeMapper("w").map("3") == timedelta(weeks=3)

        assert TimeMapper("months")("4") == relativedelta(months=4)
        assert TimeMapper("m")("4") == TimeMapper("m").map("4") == relativedelta(months=4)
