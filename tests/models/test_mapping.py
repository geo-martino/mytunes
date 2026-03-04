import re
from random import choice
from typing import Any

import pydantic
import pytest
from faker import Faker
from pydantic import TypeAdapter

from musify.exception import MusifyKeyError
from musify.models import MusifyResource
from musify.models.item.artist import Artist
from musify.models.item.track import Track
from musify.models.mapping import MusifyMapping, MusifyMutableMapping


class TestMusifyMapping:
    @pytest.fixture
    def mapping(self, models: list[MusifyResource]) -> MusifyMapping:
        mapping = MusifyMapping({key: model for model in models for key in model.unique_keys})
        assert mapping._items
        return mapping

    @pytest.fixture
    def adapter(self) -> TypeAdapter:
        return TypeAdapter(MusifyMapping)

    def test_validate_pydantic_schema(
            self,
            mapping: MusifyMapping,
            adapter: TypeAdapter[MusifyMapping],
            models: list[MusifyResource],
            faker: Faker
    ):
        assert adapter.validate_python(mapping) is mapping, "Failed to validate existing models"

        mapping_single = MusifyMapping({key: models[0] for key in models[0].unique_keys})
        assert adapter.validate_python(models[0]) == mapping_single, "Failed to validate single models"
        assert adapter.validate_python(models) == mapping, "Failed to validate list of models"
        assert adapter.validate_python(tuple(models)) == mapping, "Failed to validate tuple of models"
        assert adapter.validate_python({faker.uuid4(str): model for model in models}) == mapping, \
            "Failed to ignore keys in mapping"

    def test_validate_pydantic_schema_on_generics(self, tracks: list[Track], artists: list[Artist]):
        adapter = TypeAdapter(MusifyMapping[Any, Track])
        assert adapter.validate_python(tracks) == MusifyMapping(tracks), "Failed to validate list of tracks"

        with pytest.raises(ValueError):
            adapter.validate_python(artists)

    def test_init(self, mapping: MusifyMapping, models: list[MusifyResource], faker: Faker):
        assert MusifyMapping(mapping) is not mapping
        assert MusifyMapping(mapping) == mapping

        assert MusifyMapping(models) == mapping, "Failed to construct from list of models"
        assert MusifyMapping(iter(models)) == mapping, "Failed to construct from iterable of models"

    # noinspection PyTypeChecker
    @pytest.mark.skipif(
        tuple(map(int, (re.split(r"\D+", part)[0] for part in pydantic.__version__.split(".")))) < (2, 13, 0),
        reason="Pydantic 2.13.0+ required as lower versions do not support generics validation as expected"
        # https://github.com/pydantic/pydantic/issues/7796
    )
    def test_validates_generic_types_when_accessing(self, tracks: list[Track], artist: Artist):
        mapping = MusifyMapping[int, Track](tracks)

        with pytest.raises(ValueError):
            assert artist in mapping
        with pytest.raises(ValueError):
            assert mapping[artist]

    def test_container_methods(self, mapping: MusifyMapping, model: MusifyResource):
        assert model in mapping
        assert all(key in mapping for key in model.unique_keys)

        assert mapping.values() in mapping
        assert (key for model in mapping.values() for key in model.unique_keys) in mapping

    def test_collection_methods(self, mapping: MusifyMapping, models: list[MusifyResource]):
        assert len(mapping) == len(models)
        assert list(iter(mapping)) == list(mapping._items.keys())

    def test_equality(self, mapping: MusifyMapping, models: list[MusifyResource]):
        assert mapping is not MusifyMapping(models)
        assert mapping == MusifyMapping(models)

        initial = models[2:]
        assert mapping != MusifyMapping(initial)
        assert MusifyMapping(initial) != mapping

    def test_copy(self, mapping: MusifyMapping):
        mapping_copy = mapping.copy()
        assert isinstance(mapping_copy, mapping.__class__)
        assert mapping_copy is not mapping
        assert mapping_copy._items is not mapping._items
        assert mapping_copy._items == mapping._items

    def test_getitem(self, mapping: MusifyMapping, model: MusifyResource):
        assert mapping[model] == model
        assert mapping[next(iter(model.unique_keys))] == model

    def test_getitem_fails(self, mapping: MusifyMapping, models: list[MusifyResource]):
        initial = models[2:]
        mapping = MusifyMapping(initial)

        with pytest.raises(MusifyKeyError):
            assert mapping[models[0]]
        with pytest.raises(KeyError):
            assert mapping["unknown"]


class TestMusifyMutableMapping:
    # noinspection PyTypeChecker
    @pytest.mark.skipif(
        tuple(map(int, (re.split(r"\D+", part)[0] for part in pydantic.__version__.split(".")))) < (2, 13, 0),
        reason="Pydantic 2.13.0+ required as lower versions do not support generics validation as expected"
        # https://github.com/pydantic/pydantic/issues/7796
    )
    def test_validates_generic_types_when_mutating(
            self, track: Track, tracks: list[Track], artist: Artist, artists: list[Artist]
    ):
        mapping = MusifyMutableMapping[int, Track](tracks)

        with pytest.raises(ValueError):
            mapping["key"] = track
        with pytest.raises(ValueError):
            mapping[0] = artist
        with pytest.raises(ValueError):
            del mapping["key"]

        with pytest.raises(ValueError):
            mapping.add(artist)
        with pytest.raises(ValueError):
            mapping.update(artists)
        with pytest.raises(ValueError):
            mapping.update({id(artist): artist for artist in artists})
        with pytest.raises(ValueError):
            mapping.remove(artist)

    def test_setitem(self, model: MusifyResource):
        mapping = MusifyMutableMapping()
        assert len(mapping) == 0

        mapping[choice(list(model.unique_keys))] = model
        assert model in mapping
        assert len(mapping) == 1

        # unchanged when setting for existing resource
        mapping[choice(list(model.unique_keys))] = model
        assert model in mapping
        assert len(mapping) == 1

    def test_setitem_fails(self, model: MusifyResource):
        mapping = MusifyMutableMapping()

        with pytest.raises(ValueError):
            mapping[choice(list(model.unique_keys))] = "invalid value"

    def test_delitem(self, model: MusifyResource, models: list[MusifyResource]):
        mapping = MusifyMutableMapping(models)
        assert model in mapping

        del mapping[choice(list(model.unique_keys))]
        assert model not in mapping
        assert all(key not in mapping._items for key in model.unique_keys)

    def test_delitem_fails(self, model: MusifyResource):
        mapping = MusifyMutableMapping()
        with pytest.raises(KeyError):
            del mapping[model]

    def test_add(self, models: list[MusifyResource]):
        initial = models[2:]
        mapping = MusifyMutableMapping(initial)
        assert len(mapping) == len(initial)

        model = models[0]
        assert all(key not in mapping._items for key in model.unique_keys)

        mapping.add(model)
        assert model in mapping
        assert all(key in mapping._items for key in model.unique_keys)
        assert len(mapping) == len(initial) + 1

        # unchanged when adding existing resource
        mapping.add(choice(list(mapping.values())))
        assert len(mapping) == len(initial) + 1

    def test_add_fails(self, models: list[MusifyResource]):
        initial = models[2:]
        mapping = MusifyMutableMapping(initial)

        with pytest.raises(ValueError):
            mapping.add("invalid value")

    def test_update(self, models: list[MusifyResource]):
        initial = models[2:]
        mapping = MusifyMutableMapping(initial)
        assert not all(key in mapping._items for model in models for key in model.unique_keys)
        assert len(mapping) < len(models)

        mapping.update(models)
        assert all(key in mapping._items for model in models for key in model.unique_keys)
        assert len(mapping) == len(models)

    def test_remove(self, models: list[MusifyResource]):
        initial = models[2:]
        mapping = MusifyMutableMapping(initial)
        assert len(mapping) == len(initial)

        model = choice(list(mapping.values()))
        assert model in mapping

        mapping.remove(model)
        assert model not in mapping
        assert all(key not in mapping._items for key in model.unique_keys)
        assert len(mapping) == len(initial) - 1

        # doesn't fail when removing non-existing resource
        assert models[0] not in mapping
        mapping.remove(models[0])

    def test_clear(self, models: list[MusifyResource]):
        initial = models[2:]
        mapping = MusifyMutableMapping(initial)
        assert mapping._items

        mapping.clear()
        assert not mapping._items
