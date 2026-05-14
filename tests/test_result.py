from typing import Annotated
from unittest.mock import Mock

import pytest
import tabulate
from faker import Faker
from pytest_mock import MockerFixture

from mytunes.exception import MyTunesTypeError
from mytunes.result import LogFormatter, LenLogFormatter, MapLogFormatter, \
    Result, NamedResult, CountResult, TotalCountResult
from tests.testers import BaseModelTester


class TestLogFormatter:
    def test_condition(self, faker: Faker):
        formatter = LogFormatter(condition=lambda x: x > 5)
        assert formatter.get_value(10) == str(10)
        assert formatter.get_value(5) is None

    def test_alignment(self, faker: Faker):
        value = faker.word()

        formatter = LogFormatter(width=faker.random_int(len(value) + 5), alignment="left")
        assert formatter.get_value(value) == value.ljust(formatter.width)

        formatter = LogFormatter(width=faker.random_int(len(value) + 5), alignment="right")
        assert formatter.get_value(value) == value.rjust(formatter.width)

        formatter = LogFormatter(width=faker.random_int(len(value) + 5), alignment="centre")
        assert formatter.get_value(value) == f"{value:^{formatter.width}}"

    def test_truncate(self, faker: Faker):
        value = faker.sentence()

        result = LogFormatter(max_width=faker.random_int(3, len(value) - 5)).get_value(value)
        assert result != value
        assert len(result) < len(value)

    def test_truncate_skips(self, faker: Faker):
        value = faker.sentence()

        formatter = LogFormatter(max_width=faker.random_int(len(value) + 5))
        result = formatter.get_value(value)
        assert result == value

    def test_colour(self, faker: Faker):
        value = faker.sentence()

        colour = faker.random_element(["red", "green", "blue"])
        result = LogFormatter(style=colour).get_value(value)
        assert result != value
        assert result.startswith(f"[{colour}]") and result.endswith("[\\]")

        result = LogFormatter(style="bold").get_value(value)
        assert result != value
        assert result.startswith(f"[bold]") and result.endswith("[\\]")

    def test_colour_skips(self, faker: Faker):
        value = faker.sentence()

        formatter = LogFormatter(max_width=faker.random_int(len(value) + 5))
        result = formatter.get_value(value)
        # always adds terminating characters, just check that colour is not applied to the start of the string
        assert result.rstrip("\x1b[0m") == value

    def test_full(self, faker: Faker):
        value = faker.sentence(faker.random_int(10, 50))
        formatter = LogFormatter(
            style="bold red",
            max_width=faker.random_int(3, len(value) - 5),
            width=faker.random_int(len(value) + 5),
            alignment="right",
        )

        assert formatter.get_value(value) != value

    def test_full_skips_on_not_pretty(self, faker: Faker):
        formatter = LogFormatter(
            style="bold red",
            max_width=faker.random_int(3),
            width=faker.random_int(),
            alignment="right",
        )

        value = 12345
        assert formatter.get_value(value, pretty=False) == str(value)


class TestLenLogFormatter:
    def test_get_length(self, faker: Faker):
        value = [1, 2, 3]

        formatter = LenLogFormatter()
        assert formatter.get_value(value, pretty=False) == str(len(value))
        assert formatter.get_value(len(value), pretty=False) == str(len(value))

        value = "123"
        assert formatter.get_value(value, pretty=False) == value

    def test_get_length_fails(self, faker: Faker):
        formatter = LenLogFormatter()
        with pytest.raises(MyTunesTypeError):
            assert formatter.get_value("invalid value")


class TestMapLogFormatter:
    def test_get_value_uses_mapped_value(self, faker: Faker):
        formatter = MapLogFormatter(
            style="bold red", condition=lambda x: x > 5, value="VALUE"
        )
        assert formatter.get_value(10) == f"[bold red]VALUE[\\]"
        assert formatter.get_value(5) is None


class TestResult(BaseModelTester):
    @pytest.fixture
    def model(self, amount_formatter: LogFormatter, unit_formatter: LogFormatter, faker: Faker) -> Result:
        class ResultModel(Result):
            name: str
            amount: Annotated[int | None, amount_formatter]
            unit: Annotated[str | None, unit_formatter]

        return ResultModel(name=faker.word(), amount=faker.random_int(), unit=faker.word())

    @pytest.fixture
    def amount_formatter(self) -> LogFormatter:
        return LogFormatter(
            style="bold red", max_width=10, width=15, alignment="left"
        )

    @pytest.fixture
    def unit_formatter(self) -> LogFormatter:
        return LogFormatter(max_width=10, width=15, alignment="left")

    @pytest.fixture
    def results(self, model: Result) -> list[Result]:
        return [
            model.__class__(name="test 1", amount=5, unit="apples"),
            model.__class__(name="test 2", amount=None, unit=None),
        ]

    def test_generate_log_on_values(self, model: Result, amount_formatter: LogFormatter, unit_formatter: LogFormatter):
        result = model.__class__(name="test 1", amount=5, unit="apples")
        expected = (
            model._key_formatter.get_value("Test Result"),
            f"{amount_formatter.get_value(5)} {model._name_formatter.get_value("amount")}",
            f"{unit_formatter.get_value("apples")} {model._name_formatter.get_value("unit")}",
        )
        assert result.generate_log("Test Result") == expected

    def test_generate_log_on_none(self, model: Result, amount_formatter: LogFormatter, unit_formatter: LogFormatter):
        result = model.__class__(name="test 2", amount=None, unit=None)
        expected = (
            model._key_formatter.get_value("Test Result"),
            f"{amount_formatter.get_value("")} {model._name_formatter.get_value("amount")}",
            f"{unit_formatter.get_value("")} {model._name_formatter.get_value("unit")}",
        )
        assert result.generate_log("Test Result") == expected

    def test_generate_log_with_include_name_in_log(
            self, amount_formatter: LogFormatter, unit_formatter: LogFormatter
    ):
        unit_formatter = LogFormatter(max_width=10, width=15, alignment="left", include_name_in_log=False)

        class ResultModel(Result):
            name: str
            amount: Annotated[int | None, amount_formatter]
            unit: Annotated[str | None, unit_formatter]

        result = ResultModel(name="test 2", amount=None, unit=None)
        expected = (
            ResultModel._key_formatter.get_value("Test Result"),
            f"{amount_formatter.get_value("")} {ResultModel._name_formatter.get_value("amount")}",
            unit_formatter.get_value(""),
        )
        assert result.generate_log("Test Result") == expected

    def test_generate_table(self, model: Result, results: list[Result]):
        results = {result.name: result for result in results}
        table = Result.generate_table(results, header="Test Results")

        assert len(table.splitlines()) == len(results) + 1  # adds header row
        # adds key to each row
        assert len(table.splitlines()[1].split(" | ")) == len(next(iter(results.values())).generate_log()) + 1

    def test_sort_results(self, model: Result, results: list[Result], faker: Faker):
        expected = [
            *((result.name, result) for result in sorted(results, key=lambda result: result.name)),
            (tabulate.SEPARATING_LINE, None),
            *((result.name, result) for result in sorted(results, key=lambda result: result.name)),
        ]

        results = (
            *((result.name, result) for result in results),
            (tabulate.SEPARATING_LINE, None),
            *((result.name, result) for result in results),
        )

        assert Result._sort_results(results) == expected


class TestCountResult(BaseModelTester):
    @pytest.fixture
    def model(self, formatter: LogFormatter, faker: Faker) -> Result:
        class CountResultModel(CountResult):
            name: str
            count: Annotated[int | None, formatter]
            items: Annotated[list, formatter]

        return CountResultModel(name=faker.word(), count=faker.random_int(), items=faker.pylist())

    @pytest.fixture
    def formatter(self) -> LenLogFormatter:
        return LenLogFormatter(
            style="bold red", max_width=10, width=15, alignment="left"
        )

    @pytest.fixture
    def results(self, model: CountResult) -> list[CountResult]:
        return [
            model.__class__(name="test 1", count=5, items=[1, 2, 3]),
            model.__class__(name="test 2", count=10, items=[4, 5]),
            model.__class__(name="test 3", count=12, items=[6, 7, 8, 9]),
        ]

    def test_generate_totals_log(self, model: CountResult, results: list[CountResult], formatter: LogFormatter):
        expected = (
            model._total_key_formatter.get_value("TOTAL"),
            f"{formatter.get_value(27)} {model._name_formatter.get_value("count")}",
            f"{formatter.get_value(9)} {model._name_formatter.get_value("items")}",
        )
        assert model.generate_totals_log(results) == expected


class TestTotalCountResult(BaseModelTester):
    @pytest.fixture
    def model(self, formatter: LogFormatter, faker: Faker) -> Result:
        class TotalCountResultModel(TotalCountResult):
            name: str
            count: Annotated[int | None, formatter]
            items: Annotated[list, formatter]

        return TotalCountResultModel(name=faker.word(), count=faker.random_int(), items=faker.pylist())

    @pytest.fixture
    def formatter(self) -> LenLogFormatter:
        return LenLogFormatter(
            style="bold red", max_width=10, width=15, alignment="left"
        )

    @pytest.fixture
    def results(self, model: TotalCountResult) -> list[TotalCountResult]:
        return [
            model.__class__(name="test 1", count=5, items=[1, 2, 3]),
            model.__class__(name="test 2", count=10, items=[4, 5]),
            model.__class__(name="test 3", count=12, items=[6, 7, 8, 9]),
        ]

    def test_generate_log(
            self, model: TotalCountResult, results: list[TotalCountResult], formatter: LogFormatter
    ):
        result = model.__class__(name="test 1", count=5, items=[1, 2, 3])
        expected_total = " ".join((
            model._total_value_formatter.get_value(8),
            model._name_formatter.get_value("total"),
        ))
        expected = (
            f"{formatter.get_value(5)} {model._name_formatter.get_value("count")}",
            f"{formatter.get_value(3)} {model._name_formatter.get_value("items")}",
            expected_total
        )
        assert result.generate_log() == expected

    def test_generate_totals_log(
            self, model: TotalCountResult, results: list[TotalCountResult], formatter: LogFormatter
    ):
        expected_total = " ".join((
            model._total_value_formatter.get_value(36),
            model._name_formatter.get_value("total"),
        ))
        expected = (
            model._total_key_formatter.get_value("TOTAL"),
            f"{formatter.get_value(27)} {model._name_formatter.get_value("count")}",
            f"{formatter.get_value(9)} {model._name_formatter.get_value("items")}",
            expected_total
        )
        assert model.generate_totals_log(results) == expected


class TestNamedResult(BaseModelTester):
    @pytest.fixture
    def model(self, faker: Faker) -> NamedResult:
        return NamedResult(name=faker.word())

    @pytest.fixture
    def results(self, model: NamedResult, faker: Faker) -> list[NamedResult]:
        return [model.__class__(name=f"test {i}") for i in range(faker.random_int(1, 10))]

    @pytest.fixture
    def mock_generate_table(self, mocker: MockerFixture) -> Mock:
        return mocker.spy(Result, "generate_table")

    def test_generate_table_from_sequence(
            self, model: NamedResult, results: list[NamedResult], mock_generate_table: Mock
    ):
        expected = [(result.name, result) for result in results]

        NamedResult.generate_table(results, header=None)
        mock_generate_table.assert_called_with(results=expected, header=None)

        NamedResult.generate_table(expected, header=None)
        mock_generate_table.assert_called_with(results=expected, header=None)
