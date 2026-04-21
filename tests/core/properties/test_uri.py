from random import choice
from typing import ClassVar

import pytest
from faker import Faker
from mytunes._base.resource import ResourceModel
from mytunes.core._collection.playlist import Playlist
from mytunes.core._context import RemoteModelContext
from mytunes.core._item.album import Album
from mytunes.core._item.artist import Artist
from mytunes.core._item.track import Track
from mytunes.core.properties.uri import URI, HasMutableURI, HasImmutableURI
from mytunes.exception import MyTunesValueError
from pydantic import ValidationError
from tests.remote import SimpleURI
from tests.testers import BaseModelTester, UniqueKeyTester


class MockHasImmutableURI(HasImmutableURI[SimpleURI]):
    type: ClassVar[str] = choice((
        Track.type,
        Album.type,
        Artist.type,
        Playlist.type,
    ))


class MockHasMutableURI(HasMutableURI):
    type = MockHasImmutableURI.type


@pytest.fixture
def uri(faker: Faker) -> SimpleURI:
    return SimpleURI.create_random(MockHasImmutableURI.type)


@pytest.fixture
def uris(models: list[ResourceModel], faker: Faker) -> list[SimpleURI]:
    seen = set()
    uris = []

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


class TestURI(BaseModelTester):
    @pytest.fixture
    def model(self, uri: SimpleURI) -> URI:
        return uri

    def test_validate_source(self, uri: URI, faker: Faker):
        source = faker.word()
        while source == uri.source:
            source = faker.word()

        with pytest.raises(ValidationError):
            SimpleURI(":".join((source, uri.type, faker.pystr())))

    def test_create_unavailable_uri_on_none(self, faker: Faker):
        kind = faker.word()

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

        model = SimpleURI(":".join((model.source, model.type, model._unavailable_id)))
        assert model._unavailable_id in str(model)
        assert not model.exists

    def test_equality(self, model: SimpleURI):
        assert model == model
        assert model == str(model)
        assert model == SimpleURI(str(model))

        assert model != SimpleURI(":".join((model.source, model.type, "different_id")))
        assert model != SimpleURI(":".join((model.source, "different_type", model.id)))

        assert model == model.id
        assert model != SimpleURI(":".join((model.source, model.type, "different_id"))).id

        assert model == model.public_url
        assert model != SimpleURI(":".join((model.source, "different_type", model.id))).public_url

        assert model == model.api_url
        assert model != SimpleURI(":".join((model.source, "different_type", model.id))).api_url


class TestHasImmutableURI(UniqueKeyTester):

    @pytest.fixture
    def model(self, uri: URI) -> HasImmutableURI:
        return MockHasImmutableURI(uri=uri)

    def test_uri_field_is_read_only(self, model: HasImmutableURI, uri: URI):
        assert model.uri is uri

        with pytest.raises(ValidationError):
            model.uri = uri

    def test_validate_uri_matches_type(self, model: HasImmutableURI, faker: Faker):
        uri = SimpleURI.create_random("different_type")

        with pytest.raises(ValidationError):
            MockHasImmutableURI(uri=uri)

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
    def model(self, uris: list[URI]) -> HasMutableURI:
        return MockHasMutableURI(source=choice(uris).source, uris=uris)

    def test_validates_uris_are_from_unique_sources(self, uris: list[URI]):
        uri = choice(uris)
        different_uri = next(u for u in uris if u.source != uri.source)
        new_uri = uri.from_id(different_uri.id, different_uri.type)

        MockHasMutableURI(uris=uris)
        with pytest.raises(ValidationError):
            MockHasMutableURI(uris=[*uris, new_uri])

    def test_validate_uri_matches_type(self, faker: Faker):
        uri = SimpleURI.create_random("different_type")

        with pytest.raises(ValidationError):
            MockHasMutableURI(uri=uri)

        with pytest.raises(ValidationError):
            MockHasMutableURI(uris=[uri])

    def test_uri_on_init(self, uri: URI):
        model = MockHasMutableURI(uri=uri)
        assert model.source == uri.source
        assert model.uri is uri
        assert model.uris == {uri}

        model = MockHasMutableURI(uris=[uri])
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

    def test_set_uri_validates_type(self, model: HasMutableURI, uris: list[URI]):
        different_uri = next(uri for uri in uris if uri.source != model.source)

        with pytest.raises(MyTunesValueError):
            model.uri = str(model.uri)
        with pytest.raises(MyTunesValueError):
            model.uri = different_uri

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
        assert model == MockHasMutableURI(source=model.source, uris=uris)

        # URIs do not match
        missing_uri = next(uri for uri in uris if uri.source != model.source)
        assert model != MockHasMutableURI(source=missing_uri.source, uris=uris)

        # 2nd models doesn't have a URI set due to no URIs matching the given source
        missing_uri = next(uri for uri in uris if uri.source != model.source)
        uris = [uri for uri in uris if uri is not missing_uri]
        assert model != MockHasMutableURI(source=missing_uri.source, uris=uris)
