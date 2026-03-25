from abc import ABCMeta, abstractmethod

import pytest
from faker import Faker
from pydantic import TypeAdapter
from yarl import URL

# noinspection PyProtectedMember
from musify.models.api.types import _ApiURLSchema, _ApiURISchema
from musify.models.properties.uri import URI
from tests.models.utils import MockRemoteResource
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
    @pytest.fixture
    def adapter(self) -> TypeAdapter:
        return TypeAdapter(_ApiURLSchema[SimpleURI, MockRemoteResource])

    @pytest.fixture
    def uri(self, faker: Faker) -> URI:
        return SimpleURI.from_id(
            faker.pystr(22, 22), kind=MockRemoteResource.type
        )

    @pytest.fixture
    def expected(self, uri: URI) -> URL:
        return uri.api_url

    def test_requires_generics_definition(self):
        with pytest.raises(TypeError):
            TypeAdapter(_ApiURLSchema)


class TestApiURISchema(ApiSchemaTester[URI]):
    @pytest.fixture
    def adapter(self) -> TypeAdapter:
        return TypeAdapter(_ApiURISchema[SimpleURI, MockRemoteResource])

    @pytest.fixture
    def uri(self, faker: Faker) -> URI:
        return SimpleURI.from_id(
            faker.pystr(22, 22), kind=MockRemoteResource.type
        )

    @pytest.fixture
    def expected(self, uri: URI) -> URI:
        return uri

    def test_requires_generics_definition(self):
        with pytest.raises(TypeError):
            TypeAdapter(_ApiURISchema)
