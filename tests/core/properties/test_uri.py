from random import choice
from typing import ClassVar

import pytest
from faker import Faker
from pydantic import ValidationError

from mytunes._base.resource import ResourceModel
from mytunes.core._context import RemoteModelContext
from mytunes.core.properties.uri import URI, HasMutableURI, HasImmutableURI, UniqueURIs
from mytunes.exception import MyTunesTypeError, MyTunesValueError, MyTunesKeyError, MyTunesValidationError
from tests.remote import SimpleURI, URI_TYPES
from tests.testers import BaseModelTester, UniqueKeyTester


class MockHasImmutableURI(HasImmutableURI[SimpleURI]):
    type: ClassVar[str] = choice(URI_TYPES)


class MockHasMutableURI(HasMutableURI):
    type = MockHasImmutableURI.type


@pytest.fixture
def uri(faker: Faker) -> SimpleURI:
    return SimpleURI.create_random(MockHasImmutableURI.type)


@pytest.fixture
def uris(models: list[ResourceModel], uri: URI, faker: Faker) -> list[URI]:
    seen = set()
    uris = [uri]

    for model in range(faker.random_int(5, 10)):
        source = None
        while source is None or source in seen:
            source = faker.word()

        # noinspection PyFinal
        class AnotherSimpleURI(SimpleURI):
            _source = source

        uris.append(AnotherSimpleURI.create_random(MockHasImmutableURI.type))
        seen.add(source)

    return uris


@pytest.fixture
def uri_with_duplicate_source(uri: SimpleURI, faker: Faker) -> URI:
    return type(uri).create_random(uri.type)


@pytest.fixture
def uri_with_other_source(uri: URI, uris: list[URI]) -> URI:
    return next(u for u in uris if u.source != uri.source)


@pytest.fixture
def uri_with_other_type(uri: URI, faker: Faker) -> SimpleURI:
    other_type = choice(URI_TYPES)
    while other_type == uri.type:
        other_type = choice(URI_TYPES)

    return SimpleURI.create_random(other_type)


class TestURI(BaseModelTester):
    @pytest.fixture
    def model(self, uri: SimpleURI) -> URI:
        return uri

    def test_validate_source(self, model: URI, uri_with_other_source: URI):
        with pytest.raises(ValidationError):
            model.model_validate(str(uri_with_other_source))

    def test_validate_type(self, model: URI, faker: Faker):
        kind = faker.word()
        while kind in model._valid_types:
            kind = faker.word()

        with pytest.raises(ValidationError):
            model.model_validate(":".join((model.source, kind, faker.pystr())))

    def test_create_unavailable_uri_on_none(self, faker: Faker):
        kind = choice(URI_TYPES)

        uri = SimpleURI.model_validate(None, context=RemoteModelContext(type=kind))
        assert uri.type == kind
        assert uri.id == SimpleURI._unavailable_id

    def test_create_unavailable_uri_on_none_fails(self, faker: Faker):
        with pytest.raises(ValidationError):  # no context given
            SimpleURI.model_validate(None)

        with pytest.raises(ValidationError):  # no type given in context
            SimpleURI.model_validate(None, context=RemoteModelContext())

    def test_marks_existence(self, model: SimpleURI):
        assert model._unavailable_id not in str(model)
        assert model.exists

        model = model.model_validate(":".join((model.source, model.type, model._unavailable_id)))
        assert model._unavailable_id in str(model)
        assert not model.exists

    def test_equality(self, model: SimpleURI, uri_with_other_type: URI):
        assert model == model
        assert model == str(model)
        assert model == model.model_validate(str(model))

        assert model != model.model_validate(":".join((model.source, model.type, "different_id")))
        assert model != model.model_validate(str(uri_with_other_type))

        assert model == model.id
        assert model != model.model_validate(":".join((model.source, model.type, "different_id"))).id

        assert model == model.public_url
        assert model != model.model_validate(str(uri_with_other_type)).public_url

        assert model == model.api_url
        assert model != model.model_validate(str(uri_with_other_type)).api_url


class TestUniqueURIs:
    @pytest.fixture
    def model(self, uris: list[URI]) -> UniqueURIs:
        return UniqueURIs(uris)

    def test_container_methods(self, model: UniqueURIs, uris: list[URI]):
        assert all(uri in model for uri in uris)

    def test_collection_methods(self, model: UniqueURIs, uris: list[URI]):
        assert len(model) == len(uris)
        assert sorted(model) == sorted(uris)
        assert sorted(iter(model)) == sorted(uris)

    def test_equality(self, model: UniqueURIs, uris: list[URI]):
        assert model == set(uris)

    def test_init_fails_on_multiple_types(self, uris: list[URI], uri_with_other_type: URI):
        with pytest.raises(MyTunesValidationError):
            UniqueURIs(uris + [uri_with_other_type])

    def test_init_fails_on_duplicate_sources(self, uris: list[SimpleURI], uri_with_duplicate_source: URI):
        with pytest.raises(MyTunesValidationError):
            UniqueURIs(uris + [uri_with_duplicate_source])

    def test_add_new_source(self, uris: list[URI]):
        uri = uris.pop()
        model = UniqueURIs(uris)

        assert uri not in model
        model.add(uri)
        assert uri in model

    def test_add_existing_source_fails(self, model: UniqueURIs, uri_with_duplicate_source: URI):
        assert uri_with_duplicate_source not in model
        with pytest.raises(MyTunesKeyError):
            model.add(uri_with_duplicate_source)

    def test_add_different_type_fails(self, model: UniqueURIs, uri_with_other_type: URI):
        assert uri_with_other_type not in model
        with pytest.raises(MyTunesTypeError):
            model.add(uri_with_other_type)

    def test_replace_new_source(self, uris: list[SimpleURI], faker: Faker):
        uri = uris.pop()
        model = UniqueURIs(uris)

        assert uri not in model
        model.replace(uri)
        assert uri in model

    def test_replace_existing_source(self, model: UniqueURIs, uri_with_duplicate_source: URI):
        assert uri_with_duplicate_source not in model
        model.replace(uri_with_duplicate_source)
        assert uri_with_duplicate_source in model

    def test_replace_different_type_fails(self, model: UniqueURIs, uri_with_other_type: URI):
        assert uri_with_other_type not in model
        with pytest.raises(MyTunesTypeError):
            model.replace(uri_with_other_type)

    def test_discard(self, model: UniqueURIs, uris: list[URI], faker: Faker):
        uri = faker.random_element(uris)
        assert uri in model

        model.discard(uri)
        assert uri not in model

        model.discard(uri)
        assert uri not in model

    def test_get(self, model: UniqueURIs, uris: list[URI], faker: Faker):
        uri = faker.random_element(uris)
        assert uri in model

        assert model.get(uri.source) is uri

    def test_drop(self, model: UniqueURIs, uris: list[URI], faker: Faker):
        uri = faker.random_element(uris)
        assert uri in model

        model.drop(uri.source)
        assert uri not in model

    def test_print(self, model: UniqueURIs):
        print(repr(model))


class TestHasImmutableURI(UniqueKeyTester):

    @pytest.fixture
    def model(self, uri: URI) -> HasImmutableURI:
        return MockHasImmutableURI(uri=uri)

    def test_uri_field_is_read_only(self, model: HasImmutableURI, uri: URI):
        assert model.uri is uri

        with pytest.raises(ValidationError):
            model.uri = uri

    def test_validate_uri_matches_type(self, model: HasImmutableURI, uri_with_other_type: URI, faker: Faker):
        with pytest.raises(ValidationError):
            MockHasImmutableURI(uri=uri_with_other_type)

    def test_equality(self, model: HasImmutableURI, uri: URI):
        assert model == model
        assert model == MockHasImmutableURI(uri=uri)

        # doesn't match on string values
        assert model != str(uri)
        assert model != uri.id
        assert model != uri.api_url
        assert model != uri.public_url


class TestHasMutableURI(UniqueKeyTester):
    @pytest.fixture
    def model(self, uri: URI, uris: list[URI]) -> HasMutableURI:
        return MockHasMutableURI(source=uri.source, uris=set(uris))

    def test_validates_uris_are_from_unique_sources(self, uris: list[URI]):
        uri = choice(uris)
        different_uri = next(u for u in uris if u.source != uri.source)
        new_uri = uri.from_id(different_uri.id, different_uri.type)

        MockHasMutableURI(uris=set(uris))
        with pytest.raises(ValidationError):
            MockHasMutableURI(uris={*uris, new_uri})

    def test_validate_uri_matches_type(self, model: MockHasMutableURI, uri_with_other_type: URI, uris: list[URI]):
        with pytest.raises(ValidationError):
            MockHasMutableURI(uri=uri_with_other_type)

        with pytest.raises(ValidationError):
            MockHasMutableURI(uris={uri_with_other_type})

    def test_uri_on_init(self, uri: URI):
        model = MockHasMutableURI(uri=uri)
        assert model.source == uri.source
        assert model.uri is uri
        assert model.uris == {uri}

        model = MockHasMutableURI(uris={uri})
        assert model.source == uri.source
        assert model.uri is uri
        assert model.uris == {uri}

    def test_get_uri(self, model: HasMutableURI, uris: list[URI]):
        assert model.uris == set(uris)
        assert model.uri.source == model.source
        assert model.uri == next(uri for uri in uris if uri.source == model.source)

        model.source = None
        assert model.uri is None

    def test_set_uri(self, model: HasMutableURI, uris: list[URI]):
        assert model.uri is not None

        old_uri = model.uri
        different_uri = next(uri for uri in uris if uri.source != model.source)
        new_uri = model.uri.from_id(different_uri.id, different_uri.type)
        assert new_uri not in model.unique_keys

        model.uri = new_uri
        assert model.uri is new_uri
        assert new_uri in model.uris
        assert new_uri in model.unique_keys
        assert old_uri not in model.uris
        assert old_uri not in model.unique_keys

    def test_set_uri_as_unavailable(self, model: HasMutableURI, uris: list[URI]):
        assert model.uri is not None

        model.uri = None
        assert model.uri is None
        assert model.has_uri is False

    def test_set_uri_validates_source(self, model: HasMutableURI, uri_with_other_source: URI, uris: list[URI]):
        with pytest.raises(MyTunesTypeError):
            model.uri = str(model.uri)

        with pytest.raises(MyTunesTypeError):
            model.uri = uri_with_other_source

    def test_set_uri_validates_type(self, model: HasMutableURI, uri_with_other_type: URI, uris: list[URI]):
        with pytest.raises(MyTunesTypeError):
            model.uri = str(model.uri)
        with pytest.raises(MyTunesTypeError):
            model.uri = uri_with_other_type

    def test_set_uri_sets_source(self, model: HasMutableURI, uri: URI):
        model.source = None  # no current source, should set source from URI

        model.uri = uri
        assert model.source == uri.source

    def test_delete_uri(self, model: HasMutableURI, uris: list[URI]):
        uri = model.uri
        del model.uri
        assert uri not in model.uris

    def test_has_uri(self, model: HasMutableURI, uris: list[URI]):
        assert model.uri.exists
        assert model.has_uri is True

        uri = model.uri.from_id(model.uri._unavailable_id, model.uri.type)
        model.uri = uri
        assert model.uri is None
        assert model.has_uri is False

        del model.uri
        assert model.uri is None
        assert model.has_uri is None

    def test_equality(self, model: HasMutableURI, uris: list[URI]):
        assert model == model
        assert model == MockHasMutableURI(source=model.source, uris=set(uris))

        # URIs do not match
        missing_uri = next(uri for uri in uris if uri.source != model.source)
        assert model != MockHasMutableURI(source=missing_uri.source, uris=set(uris))

        # 2nd models doesn't have a URI set due to no URIs matching the given source
        missing_uri = next(uri for uri in uris if uri.source != model.source)
        uris = [uri for uri in uris if uri is not missing_uri]
        assert model != MockHasMutableURI(source=missing_uri.source, uris=set(uris))
