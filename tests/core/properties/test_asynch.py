from asyncio import Semaphore

import pytest
from mytunes.core.properties.asynch import SemaphoreT
from pydantic import TypeAdapter


class TestSemaphoreSchema:
    @pytest.fixture(scope="class")
    def adapter(self) -> TypeAdapter[SemaphoreT]:
        return TypeAdapter(SemaphoreT)

    def test_validation(self, adapter: TypeAdapter):
        sem = adapter.validate_python(10)
        assert isinstance(sem, Semaphore)
        assert sem._value == 10

    def test_serialisation(self, adapter: TypeAdapter):
        sem = Semaphore(10)
        assert adapter.serializer.to_json(sem) == b"10"
        assert adapter.serializer.to_python(sem) == sem
