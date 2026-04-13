from abc import ABCMeta, abstractmethod

import pytest
from faker import Faker
# noinspection PyProtectedMember
from mytunes._models.api.types import ApiURLSchema, ApiURISchema
from mytunes._models.properties.uri import URI
from pydantic import TypeAdapter
from tests.remote import SimpleURI, MockRemoteResource
from yarl import URL


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

    @staticmethod
    def test_from_api_url(adapter: TypeAdapter, uri: URI, expected: T):
        assert adapter.validate_python(str(uri.api_url)) == expected
        assert adapter.validate_python(uri.api_url) == expected

    @staticmethod
    def test_from_public_url(adapter: TypeAdapter, uri: URI, expected: T):
        assert adapter.validate_python(str(uri.api_url)) == expected
        assert adapter.validate_python(uri.api_url) == expected

    @staticmethod
    def test_from_uri(adapter: TypeAdapter, uri: URI, expected: T):
        assert adapter.validate_python(str(uri)) == expected
        assert adapter.validate_python(uri) == expected

    @staticmethod
    def test_from_resource(adapter: TypeAdapter, uri: URI, expected: T):
        resource = MockRemoteResource(uri=uri)
        assert adapter.validate_python(resource) == expected

    @staticmethod
    def test_from_id(adapter: TypeAdapter, uri: URI, expected: T):
        assert adapter.validate_python(uri.id) == expected


class TestApiURLSchema(ApiSchemaTester[URL]):
    @pytest.fixture(scope="class")
    def adapter(self) -> TypeAdapter:
        return TypeAdapter(ApiURLSchema[SimpleURI, MockRemoteResource])

    @pytest.fixture(scope="class")
    def uri(self, faker: Faker) -> URI:
        return SimpleURI.create_random(MockRemoteResource.type)

    @pytest.fixture(scope="class")
    def expected(self, uri: URI) -> URL:
        return uri.api_url

    def test_requires_generics_definition(self):
        with pytest.raises(TypeError):
            TypeAdapter(ApiURLSchema)


class TestApiURISchema(ApiSchemaTester[URI]):
    @pytest.fixture(scope="class")
    def adapter(self) -> TypeAdapter:
        return TypeAdapter(ApiURISchema[SimpleURI, MockRemoteResource])

    @pytest.fixture(scope="class")
    def uri(self, faker: Faker) -> URI:
        return SimpleURI.create_random(MockRemoteResource.type)

    @pytest.fixture(scope="class")
    def expected(self, uri: URI) -> URI:
        return uri

    def test_requires_generics_definition(self):
        with pytest.raises(TypeError):
            TypeAdapter(ApiURISchema)
