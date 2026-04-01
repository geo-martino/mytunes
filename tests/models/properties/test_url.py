import json

import pytest
from pydantic import TypeAdapter
from yarl import URL

from musify.models.url import HttpURL


class TestURLSchema:
    @pytest.fixture(scope="class")
    def adapter(self) -> TypeAdapter[HttpURL]:
        return TypeAdapter(HttpURL)

    def test_validation(self, adapter: TypeAdapter):
        value = "https://www.example.com/query"
        url = adapter.validate_python(value)
        assert isinstance(url, URL)
        assert url == URL(value)

    def test_serialisation(self, adapter: TypeAdapter):
        value = "https://www.example.com/query"
        url = URL(value)
        assert adapter.serializer.to_json(url) == json.dumps(value).encode()
        assert adapter.serializer.to_python(url) == url
