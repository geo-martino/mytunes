import pytest
from faker import Faker
from pydantic import TypeAdapter
from yarl import URL

from musify.models.properties.uri import URI
from musify.remote.api._types import ApiURLSchema
from tests.remote.api.utils import MockRemoteResource
from tests.utils import SimpleURI


class TestApiURLSchema:
    @pytest.fixture
    def adapter(self) -> TypeAdapter:
        return TypeAdapter(ApiURLSchema[SimpleURI, MockRemoteResource])

    @pytest.fixture
    def uri(self, faker: Faker) -> URI:
        return SimpleURI.from_id(
            faker.random_int(int(10e9), int(10e10)), kind=MockRemoteResource.type
        )

    @pytest.fixture
    def expected(self, uri: URI) -> URL:
        return uri.api_url

    def test_requires_generics_definition(self):
        with pytest.raises(TypeError):
            TypeAdapter(ApiURLSchema)

    def test_from_url(self, adapter: TypeAdapter, expected: URL):
        assert adapter.validate_python(str(expected)) == expected
        assert adapter.validate_python(expected) == expected

    def test_from_uri(self, adapter: TypeAdapter, uri: URI, expected: URL):
        assert adapter.validate_python(str(expected)) == expected
        assert adapter.validate_python(expected) == expected

    def test_from_resource(self, adapter: TypeAdapter, uri: URI, expected: URL):
        resource = MockRemoteResource(uri=uri)
        assert adapter.validate_python(resource) == expected

    def test_from_id(self, adapter: TypeAdapter, uri: URI, expected: URL):
        assert adapter.validate_python(uri.id) == expected
