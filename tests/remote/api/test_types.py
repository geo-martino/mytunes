from abc import ABCMeta, abstractmethod

import pytest
from faker import Faker
from pydantic import TypeAdapter
from yarl import URL

from musify.models.properties.uri import URI
from musify.remote.api._types import ApiURLSchema, ApiURISchema
from tests.remote.api.utils import MockRemoteResource
from tests.utils import SimpleURI


class ApiSchemaTester[T](metaclass=ABCMeta):
    @abstractmethod
    def adapter(self) -> TypeAdapter:
        raise NotImplementedError

    @abstractmethod
    def uri(self, faker: Faker) -> URI:
        raise NotImplementedError

    @abstractmethod
    def expected(self, uri: URI) -> T:
        raise NotImplementedError

    @abstractmethod
    def test_requires_generics_definition(self):
        raise NotImplementedError

    def test_from_api_url(self, adapter: TypeAdapter, uri: URI, expected: T):
        assert adapter.validate_python(str(uri.api_url)) == expected
        assert adapter.validate_python(uri.api_url) == expected

    def test_from_public_url(self, adapter: TypeAdapter, uri: URI, expected: T):
        assert adapter.validate_python(str(uri.api_url)) == expected
        assert adapter.validate_python(uri.api_url) == expected

    def test_from_uri(self, adapter: TypeAdapter, uri: URI, expected: T):
        assert adapter.validate_python(str(uri)) == expected
        assert adapter.validate_python(uri) == expected

    def test_from_resource(self, adapter: TypeAdapter, uri: URI, expected: T):
        resource = MockRemoteResource(uri=uri)
        assert adapter.validate_python(resource) == expected

    def test_from_id(self, adapter: TypeAdapter, uri: URI, expected: T):
        assert adapter.validate_python(uri.id) == expected


class TestApiURLSchema(ApiSchemaTester[URL]):
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


class TestApiURISchema(ApiSchemaTester[URI]):
    @pytest.fixture
    def adapter(self) -> TypeAdapter:
        return TypeAdapter(ApiURISchema[SimpleURI, MockRemoteResource])

    @pytest.fixture
    def uri(self, faker: Faker) -> URI:
        return SimpleURI.from_id(
            faker.random_int(int(10e9), int(10e10)), kind=MockRemoteResource.type
        )

    @pytest.fixture
    def expected(self, uri: URI) -> URI:
        return uri

    def test_requires_generics_definition(self):
        with pytest.raises(TypeError):
            TypeAdapter(ApiURISchema)
