import re
from random import choice
from typing import Any

import pydantic
import pytest
from faker import Faker
from mytunes.local._collection.playlist import LocalPlaylistFile
from pydantic import TypeAdapter, ValidationError
from pytest_mock import MockerFixture

from mytunes._models import ResourceModel
from mytunes._models.item.artist import Artist
from mytunes._models.item.track import Track
from mytunes._models.mapping import UniqueMapping, MutableUniqueMapping
from mytunes.exception import MyTunesKeyError


class TestUniqueMapping:
    @pytest.fixture
    def mapping(self, models: list[ResourceModel]) -> UniqueMapping:
        mapping = UniqueMapping({key: model for model in models for key in model.unique_keys})
        assert mapping._items
        return mapping

    @pytest.fixture(scope="class")
    def adapter(self) -> TypeAdapter:
        return TypeAdapter(UniqueMapping)

    def test_validate_pydantic_schema(
            self,
            mapping: UniqueMapping,
            adapter: TypeAdapter[UniqueMapping],
            models: list[ResourceModel],
            faker: Faker
    ):
        assert adapter.validate_python(mapping) is mapping, "Failed to validate existing models"

        mapping_single = UniqueMapping({key: models[0] for key in models[0].unique_keys})
        assert adapter.validate_python(models[0]) == mapping_single, "Failed to validate single models"
        assert adapter.validate_python(models) == mapping, "Failed to validate list of models"
        assert adapter.validate_python(tuple(models)) == mapping, "Failed to validate tuple of models"
        assert adapter.validate_python({faker.uuid4(str): model for model in models}) == mapping, \
            "Failed to ignore keys in mapping"

    def test_validate_pydantic_schema_on_generics(self, tracks: list[Track], artists: list[Artist]):
        adapter = TypeAdapter(UniqueMapping[Any, Track])
        assert adapter.validate_python(tracks) == UniqueMapping(tracks), "Failed to validate list of tracks"

        with pytest.raises(pydantic.ValidationError):
            adapter.validate_python(artists)

    def test_init(self, mapping: UniqueMapping, models: list[ResourceModel], faker: Faker):
        assert UniqueMapping(mapping) is not mapping
        assert UniqueMapping(mapping) == mapping

        assert UniqueMapping(models) == mapping, "Failed to construct from list of models"
        assert UniqueMapping(iter(models)) == mapping, "Failed to construct from iterable of models"

    # noinspection PyTypeChecker
    @pytest.mark.skipif(
        tuple(map(int, (re.split(r"\D+", part)[0] for part in pydantic.__version__.split(".")))) < (2, 13, 0),
        reason="Pydantic 2.13.0+ required as lower versions do not support generics validation as expected"
        # https://github.com/pydantic/pydantic/issues/7796
    )
    def test_validates_generic_types_when_accessing(self, tracks: list[Track], artist: Artist):
        mapping = UniqueMapping[int, Track](tracks)

        with pytest.raises(ValidationError):
            assert artist in mapping
        with pytest.raises(ValidationError):
            assert mapping[artist]

    def test_container_methods(self, mapping: UniqueMapping, model: ResourceModel):
        assert model in mapping
        assert all(key in mapping for key in model.unique_keys)

        assert mapping.values() in mapping
        assert (key for model in mapping.values() for key in model.unique_keys) in mapping

    def test_collection_methods(self, mapping: UniqueMapping, models: list[ResourceModel]):
        assert len(mapping) == len(models)
        assert list(iter(mapping)) == list(mapping._items.keys())

    def test_equality(self, mapping: UniqueMapping, models: list[ResourceModel]):
        assert mapping is not UniqueMapping(models)
        assert mapping == UniqueMapping(models)

        initial = models[2:]
        assert mapping != UniqueMapping(initial)
        assert UniqueMapping(initial) != mapping

    def test_copy(self, mapping: UniqueMapping):
        mapping_copy = mapping.copy()
        assert isinstance(mapping_copy, mapping.__class__)
        assert mapping_copy is not mapping
        assert mapping_copy._items is not mapping._items
        assert mapping_copy._items == mapping._items

    def test_getitem(self, mapping: UniqueMapping, model: ResourceModel):
        assert mapping[model] == model
        assert mapping[next(iter(model.unique_keys))] == model

    def test_getitem_fails(self, mapping: UniqueMapping, models: list[ResourceModel]):
        initial = models[2:]
        mapping = UniqueMapping(initial)

        with pytest.raises(MyTunesKeyError):
            assert mapping[models[0]]
        with pytest.raises(KeyError):
            assert mapping["unknown"]

    def test_update(self, models: list[ResourceModel]):
        initial = models[2:]
        mapping = UniqueMapping(initial)
        assert not all(key in mapping._items for model in models for key in model.unique_keys)
        assert len(mapping) < len(models)

        mapping._update(models)
        assert all(key in mapping._items for model in models for key in model.unique_keys)
        assert len(mapping) == len(models)

    def test_replace(self, models: list[ResourceModel], faker: Faker):
        initial = faker.random_elements(models, unique=True)
        mapping = UniqueMapping(initial)
        assert all(key in mapping._items for model in initial for key in model.unique_keys)

        new = faker.random_elements(models, unique=True)
        mapping._replace(new)
        assert all(key in mapping._items for model in new for key in model.unique_keys)


class TestMutableUniqueMapping:
    # noinspection PyTypeChecker
    @pytest.mark.skipif(
        tuple(map(int, (re.split(r"\D+", part)[0] for part in pydantic.__version__.split(".")))) < (2, 13, 0),
        reason="Pydantic 2.13.0+ required as lower versions do not support generics validation as expected"
        # https://github.com/pydantic/pydantic/issues/7796
    )
    def test_validates_generic_types_when_mutating(
            self, track: Track, tracks: list[Track], artist: Artist, artists: list[Artist]
    ):
        mapping = MutableUniqueMapping[int, Track](tracks)

        with pytest.raises(ValidationError):
            mapping["key"] = track
        with pytest.raises(ValidationError):
            mapping[0] = artist
        with pytest.raises(ValidationError):
            del mapping["key"]

        with pytest.raises(ValidationError):
            mapping.add(artist)
        with pytest.raises(ValidationError):
            mapping.update(artists)
        with pytest.raises(ValidationError):
            mapping.update({id(artist): artist for artist in artists})
        with pytest.raises(ValidationError):
            mapping.remove(artist)

    def test_setitem(self, model: ResourceModel):
        mapping = MutableUniqueMapping()
        assert len(mapping) == 0

        mapping[choice(list(model.unique_keys))] = model
        assert model in mapping
        assert len(mapping) == 1

        # unchanged when setting for existing resource
        mapping[choice(list(model.unique_keys))] = model
        assert model in mapping
        assert len(mapping) == 1

    def test_setitem_fails(self, model: ResourceModel):
        mapping = MutableUniqueMapping()

        with pytest.raises(ValidationError):
            mapping[choice(list(model.unique_keys))] = "invalid value"

    def test_delitem(self, model: ResourceModel, models: list[ResourceModel]):
        mapping = MutableUniqueMapping(models)
        assert model in mapping

        del mapping[choice(list(model.unique_keys))]
        assert model not in mapping
        assert all(key not in mapping._items for key in model.unique_keys)

    def test_delitem_fails(self, model: ResourceModel):
        mapping = MutableUniqueMapping()
        with pytest.raises(KeyError):
            del mapping[model]

    def test_add(self, models: list[ResourceModel]):
        initial = models[2:]
        mapping = MutableUniqueMapping(initial)
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

    def test_add_fails(self, models: list[ResourceModel]):
        initial = models[2:]
        mapping = MutableUniqueMapping(initial)

        with pytest.raises(ValidationError):
            mapping.add("invalid value")

    def test_update(self, models: list[ResourceModel], mocker: MockerFixture):
        mock_update = mocker.spy(UniqueMapping, "_update")

        mapping = MutableUniqueMapping(models)
        mapping.update(models)
        mock_update.assert_called_once()

    def test_remove(self, models: list[ResourceModel]):
        initial = models[2:]
        mapping = MutableUniqueMapping(initial)
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

    def test_remove_on_unique_key_change(self, models: list[ResourceModel], faker: Faker):
        initial = [
            LocalPlaylistFile(path=faker.file_path()),
            LocalPlaylistFile(path=faker.file_path()),
            LocalPlaylistFile(path=faker.file_path()),
        ]
        mapping = MutableUniqueMapping(initial)
        assert len(mapping) == sum(len(it.unique_keys) for it in initial)

        model = choice(list(mapping.values()))
        assert model in mapping

        model.path = faker.file_path()  # change unique key
        mapping.remove(model)
        assert model not in mapping
        assert all(key not in mapping._items for key in model.unique_keys)
        assert len(mapping) == sum(len(it.unique_keys) for it in initial) - len(model.unique_keys)

    def test_clear(self, models: list[ResourceModel]):
        initial = models[2:]
        mapping = MutableUniqueMapping(initial)
        assert mapping._items

        mapping.clear()
        assert not mapping._items

    def test_replace(self, models: list[ResourceModel], mocker: MockerFixture):
        mock_replace = mocker.spy(UniqueMapping, "_replace")

        mapping = MutableUniqueMapping(models)
        mapping.replace(models)
        mock_replace.assert_called_once()
