from random import choice

import pytest

from musify.exception import MusifyValueError
from musify.models import MusifyRootModel, MusifyModel
from musify.models.properties.uri import URI, HasURI, HasMutableURI
from tests.models.testers import MusifyModelTester, UniqueKeyTester
from tests.utils import SimpleURI


class TestURI(MusifyModelTester):
    @pytest.fixture
    def model(self, uri: SimpleURI) -> URI:
        return uri

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

        assert model == model.url
        assert model != SimpleURI(":".join((model.source, "different_type", model.id))).url

        assert model == model.href
        assert model != SimpleURI(":".join((model.source, "different_type", model.id))).href


class TestHasURI(UniqueKeyTester):
    @pytest.fixture
    def model(self, uri: URI) -> HasURI:
        return HasURI(uri=uri)

    def test_uri_field_is_read_only(self, model: HasURI, uri: URI):
        assert model.uri is uri

        with pytest.raises(AttributeError):
            # noinspection PyPropertyAccess
            model.uri = uri

    def test_equality(self, model: HasURI, uri: URI):
        assert model == model
        assert model == HasURI(uri=uri)

        # doesn't match on string values
        assert model != str(uri)
        assert model != uri.id
        assert model != uri.href
        assert model != uri.url


class TestHasMutableURI(UniqueKeyTester):
    @pytest.fixture
    def model(self, uris: list[URI]) -> HasMutableURI:
        return HasMutableURI(source=choice(uris).source, uris=uris)

    def test_validates_uris_are_from_unique_sources(self, uris: list[URI]):
        uri = choice(uris)
        different_uri = next(u for u in uris if u.source != uri.source)
        new_uri = SimpleURI.from_id(different_uri.id, different_uri.type, uri.source)

        HasMutableURI(uris=uris)
        with pytest.raises(ValueError):
            HasMutableURI(uris=[*uris, new_uri])

    def test_get_uri(self, model: HasMutableURI, uris: list[URI]):
        assert model.uris == uris
        assert model.uri.source == model.source
        assert model.uri == next(uri for uri in uris if uri.source == model.source)

        model.source = None
        assert model.uri is None

    def test_set_uri(self, model: HasMutableURI, uris: list[URI]):
        assert model.uri is not None

        old_uri = model.uri
        different_uri = next(uri for uri in uris if uri.source != model.source)
        new_uri = SimpleURI.from_id(different_uri.id, different_uri.type, model.uri.source)
        assert new_uri not in model.unique_keys

        model.uri = new_uri
        assert model.uri is new_uri
        assert new_uri in model.uris
        assert new_uri in model.unique_keys
        assert old_uri not in model.uris
        assert old_uri not in model.unique_keys

    def test_set_uri_validates_type(self, model: HasMutableURI, uris: list[URI]):
        different_uri = next(uri for uri in uris if uri.source != model.source)

        with pytest.raises(MusifyValueError):
            model.uri = str(model.uri)
        with pytest.raises(MusifyValueError):
            model.uri = different_uri

    def test_set_uri_sets_source(self, model: HasMutableURI, uris: list[URI]):
        model.source = None  # no current source, should set source from URI
        uri = choice(uris)

        model.uri = uri
        assert model.source == uri.source

    def test_delete_uri(self, model: HasMutableURI, uris: list[URI]):
        uri = model.uri
        del model.uri
        assert uri not in model.uris

    # noinspection PyTestUnpassedFixture
    def test_has_uri(self, model: HasMutableURI, uris: list[URI]):
        assert model.uri.exists
        assert model.has_uri is True

        uri = SimpleURI.from_id(model.uri._unavailable_id, model.uri.type, model.source)
        model.uri = uri
        assert model.uri is None
        assert model.has_uri is False

        del model.uri
        assert model.uri is None
        assert model.has_uri is None

    def test_equality(self, model: HasMutableURI, uris: list[URI]):
        assert model == model
        assert model == HasMutableURI(source=model.source, uris=uris)

        # URIs do not match
        missing_uri = next(uri for uri in uris if uri.source != model.source)
        assert model != HasMutableURI(source=missing_uri.source, uris=uris)

        # 2nd models doesn't have a URI set due to no URIs matching the given source
        missing_uri = next(uri for uri in uris if uri.source != model.source)
        assert model != HasMutableURI(source=missing_uri.source, uris=[uri for uri in uris if uri is not missing_uri])
