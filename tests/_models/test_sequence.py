import re
from random import choice
from typing import Any

import pydantic
import pytest
from faker import Faker
from mytunes._models import ResourceModel
from mytunes._models.item.artist import Artist
from mytunes._models.item.track import Track
from mytunes._models.sequence import UniqueSequence, MutableUniqueSequence
from pydantic import TypeAdapter, ValidationError
from tests.utils import split_list


class TestUniqueSequence:
    @pytest.fixture
    def sequence(self, models: list[ResourceModel]) -> UniqueSequence:
        sequence = UniqueSequence(models)
        assert sequence._items
        return sequence

    @pytest.fixture(scope="class")
    def adapter(self) -> TypeAdapter:
        return TypeAdapter(UniqueSequence)

    def test_validate_pydantic_schema(
            self,
            sequence: UniqueSequence,
            adapter: TypeAdapter[UniqueSequence],
            models: list[ResourceModel],
            faker: Faker
    ):
        assert adapter.validate_python(sequence) is sequence, "Failed to validate existing models"

        sequence_single = UniqueSequence([models[0]])
        assert adapter.validate_python(models[0]) == sequence_single, "Failed to validate single models"
        assert adapter.validate_python(models) == sequence, "Failed to validate list of models"
        assert adapter.validate_python(tuple(models)) == sequence, "Failed to validate tuple of models"

    def test_validate_pydantic_schema_on_generics(self, tracks: list[Track], artists: list[Artist]):
        adapter = TypeAdapter(UniqueSequence[Any, Track])
        assert adapter.validate_python(tracks) == UniqueSequence(tracks), "Failed to validate list of tracks"

        with pytest.raises(ValidationError):
            adapter.validate_python(artists)

    def test_init(self, sequence: UniqueSequence, models: list[ResourceModel], faker: Faker):
        assert UniqueSequence(sequence) is not sequence
        assert UniqueSequence(sequence) == sequence

        assert UniqueSequence(models) == sequence, "Failed to construct from list of models"
        assert UniqueSequence(iter(models)) == sequence, "Failed to construct from iterable of models"
        mapping = {faker.uuid4(str): model for model in models}
        assert UniqueSequence(mapping) == sequence, "Failed to construct from mapping of models"

    # noinspection PyTypeChecker
    @pytest.mark.skipif(
        tuple(map(int, (re.split(r"\D+", part)[0] for part in pydantic.__version__.split(".")))) < (2, 13, 0),
        reason="Pydantic 2.13.0+ required as lower versions do not support generics validation as expected"
        # https://github.com/pydantic/pydantic/issues/7796
    )
    def test_validates_generic_types_when_accessing(self, tracks: list[Track], artist: Artist, artists: list[Artist]):
        sequence = UniqueSequence[int, Track](tracks)

        with pytest.raises(ValidationError):
            assert artist in sequence
        with pytest.raises(ValidationError):
            assert sequence[artist]

        with pytest.raises(ValidationError):
            assert sequence.intersection(artists)
        with pytest.raises(ValidationError):
            assert sequence.difference(artists)
        with pytest.raises(ValidationError):
            assert sequence.outer_difference(artists)

    def test_container_methods(self, sequence: UniqueSequence, model: ResourceModel):
        assert model in sequence
        assert all(key in sequence for key in model.unique_keys)

        assert sequence._items in sequence
        assert (key for model in sequence._items for key in model.unique_keys) in sequence

    def test_collection_methods(self, sequence: UniqueSequence, models: list[ResourceModel]):
        assert len(sequence) == len(models)
        assert list(iter(sequence)) == sequence._items

    def test_equality(self, sequence: UniqueSequence, models: list[ResourceModel]):
        assert sequence is not UniqueSequence(models)
        assert sequence == UniqueSequence(models)

        initial = models[2:]
        assert sequence != UniqueSequence(initial)
        assert UniqueSequence(initial) != sequence

    def test_copy(self, sequence: UniqueSequence):
        sequence_copy = sequence.copy()
        assert isinstance(sequence_copy, sequence.__class__)
        assert sequence_copy is not sequence
        assert sequence_copy._items is not sequence._items
        assert sequence_copy._items == sequence._items

    def test_getitem(self, sequence: UniqueSequence, models: list[ResourceModel]):
        assert sequence[0] == models[0]
        assert sequence[:2] == models[:2]
        assert sequence[next(iter(models[0].unique_keys))] == models[0]

    def test_getitem_fails(self, sequence: UniqueSequence, models: list[ResourceModel]):
        initial = models[2:]
        sequence = UniqueSequence(initial)

        with pytest.raises(KeyError):
            assert sequence[next(iter(models[0].unique_keys))]
        with pytest.raises(KeyError):
            assert sequence["unknown"]

    @staticmethod
    def test_intersection(models: list[ResourceModel]):
        initial, other = map(tuple, split_list(models, 2))
        sequence = UniqueSequence(initial)

        assert sequence.intersection(initial) == initial
        assert sequence.intersection(other) == ()
        assert sequence.intersection(other + initial[2:]) == initial[2:]

    @staticmethod
    def test_difference(models: list[ResourceModel]):
        initial, other = map(tuple, split_list(models, 2))
        sequence = UniqueSequence(initial)

        assert sequence.difference(initial) == ()
        assert sequence.difference(other) == initial
        assert sequence.difference(other + initial[2:]) == initial[:2]

    @staticmethod
    def test_outer_difference(models: list[ResourceModel]):
        initial, other = map(tuple, split_list(models, 2))
        sequence = UniqueSequence(initial)

        assert sequence.outer_difference(initial) == ()
        assert sequence.outer_difference(other) == other
        assert sequence.outer_difference(other + initial[2:]) == other


class TestMutableUniqueSequence:
    # noinspection PyTypeChecker
    @pytest.mark.skipif(
        tuple(map(int, (re.split(r"\D+", part)[0] for part in pydantic.__version__.split(".")))) < (2, 13, 0),
        reason="Pydantic 2.13.0+ required as lower versions do not support generics validation as expected"
        # https://github.com/pydantic/pydantic/issues/7796
    )
    def test_validates_generic_types_when_mutating(self, tracks: list[Track], artist: Artist, artists: list[Artist]):
        sequence = MutableUniqueSequence[int, Track](tracks)

        with pytest.raises(ValidationError):
            sequence[0] = artist
        with pytest.raises(ValidationError):
            sequence + artists
        with pytest.raises(ValidationError):
            sequence += artists
        with pytest.raises(ValidationError):
            sequence - artists
        with pytest.raises(ValidationError):
            sequence -= artists
        with pytest.raises(ValidationError):
            sequence | artists
        with pytest.raises(ValidationError):
            sequence |= artists

        with pytest.raises(ValidationError):
            sequence.append(artist)
        with pytest.raises(ValidationError):
            sequence.extend(artists)
        with pytest.raises(ValidationError):
            sequence.insert(0, artist)
        with pytest.raises(ValidationError):
            sequence.merge(artists)
        with pytest.raises(ValidationError):
            sequence.merge(sequence, reference=artists)
        with pytest.raises(ValidationError):
            sequence.remove(artist)

    def test_setitem(self, models: list[ResourceModel]):
        initial, other = split_list(models, 2)
        sequence = MutableUniqueSequence(initial)

        model = choice(other)
        assert model not in sequence

        sequence[0] = model
        assert model in sequence
        assert sequence._items[0] == model
        assert all(key in sequence._items_mapped for key in model.unique_keys)

        sequence[0:2] = initial[1:3]
        assert all(m in sequence for m in initial[1:3])
        assert sequence._items[0:2] == initial[1:3]
        assert all(key in sequence._items_mapped for m in initial[1:3] for key in m.unique_keys)

    def test_setitem_fails(self, models: list[ResourceModel]):
        initial = models[:3]
        sequence = MutableUniqueSequence(initial)

        with pytest.raises(ValidationError):
            sequence[0] = "invalid value"

    def test_delitem(self, models: list[ResourceModel]):
        sequence = MutableUniqueSequence(models)
        model = models[0]
        assert model in sequence

        del sequence[sequence._items.index(model)]
        assert model not in sequence
        assert all(key not in sequence._items_mapped for key in model.unique_keys)

        del sequence[0:2]
        assert all(model not in sequence for model in models[1:3])
        assert all(key not in sequence._items_mapped for m in models[1:3] for key in m.unique_keys)

    def test_delitem_fails(self):
        sequence = MutableUniqueSequence()
        with pytest.raises(KeyError):
            del sequence[0]

    def test_mutable_dunder_methods(self, models: list[ResourceModel]):
        initial, other = split_list(models, 2)
        sequence = MutableUniqueSequence(initial)
        original = sequence.copy()

        assert sequence + sequence == sequence._items + sequence._items
        assert sequence - sequence == []
        assert sequence._items == original._items
        assert sequence._items_mapped == original._items_mapped

        sequence += other
        assert len(sequence) == len(original) + len(other)
        assert sequence._items != original._items
        assert sequence._items_mapped != original._items_mapped
        assert all(key in sequence._items_mapped for m in other for key in m.unique_keys)

        sequence -= original
        assert len(sequence) == len(other)
        assert sequence._items == other
        assert all(key in sequence._items_mapped for m in other for key in m.unique_keys)

    def test_append(self, models: list[ResourceModel]):
        initial = models[3:]
        sequence = MutableUniqueSequence(initial)
        original_length = len(sequence._items)

        model = models[0]
        assert model not in sequence

        sequence.append(model)
        assert len(sequence) == original_length + 1
        assert model in sequence
        assert sequence._items[-1] == model
        assert all(key in sequence._items_mapped for key in model.unique_keys)
        expected_keys = set(sequence._items_mapped)

        # adds duplicates
        sequence.append(model)
        assert len(sequence) == original_length + 2
        assert sequence._items[-1] == model
        assert sequence._items[-2] == model
        assert sequence._items_mapped.keys() == expected_keys

    def test_extend(self, models: list[ResourceModel]):
        initial, other = split_list(models, 2)
        sequence = MutableUniqueSequence(initial)
        original_length = len(sequence._items)
        assert all(m not in sequence for m in other)

        sequence.extend(other)
        assert len(sequence) == original_length + len(other)
        assert all(m in sequence for m in other)
        assert sequence._items[-len(other):] == other
        assert all(key in sequence._items_mapped for m in other for key in m.unique_keys)
        expected_keys = set(sequence._items_mapped)

        # adds duplicates
        sequence.extend(other)
        assert len(sequence) == original_length + 2 * len(other)
        assert sequence._items[-len(other):] == other
        assert sequence._items[-len(other) * 2:-len(other)] == other
        assert sequence._items_mapped.keys() == expected_keys

    def test_insert(self, models: list[ResourceModel]):
        initial = models[3:]
        sequence = MutableUniqueSequence(initial)
        original_length = len(sequence._items)

        model = models[0]
        assert model not in sequence

        sequence.insert(2, model)
        assert len(sequence) == original_length + 1
        assert model in sequence
        assert sequence._items[2] == model
        assert all(key in sequence._items_mapped for key in model.unique_keys)
        expected_keys = set(sequence._items_mapped)

        # adds duplicates
        sequence.insert(2, model)
        assert len(sequence) == original_length + 2
        assert sequence._items[2] == model
        assert sequence._items[3] == model
        assert sequence._items_mapped.keys() == expected_keys

    def test_merge_without_reference(self, models: list[ResourceModel]):
        initial, other, overlap = split_list(models, 2, 3)
        other_original = other.copy()

        sequence = MutableUniqueSequence(initial)
        sequence.merge(other)

        assert all(model in sequence for model in other)
        assert all(sequence.count(model) for model in overlap)

        # given sequence remains unchanged
        assert other == other_original

    def test_merge_with_reference(self, models: list[ResourceModel]):
        for i, model in enumerate(models):
            model.name = str(i)

        initial, other, reference = split_list(models, 2, 6)
        other = other[:len(reference) // 2]
        reference_original = reference.copy()
        other_original = other.copy()

        expected_keep = [model for model in initial if model not in reference]
        expected_remove = [model for model in reference if model not in other]
        expected_add = [model for model in other if model not in initial]

        sequence = MutableUniqueSequence(initial)
        sequence.merge(other, reference=reference)

        assert all(model in sequence for model in expected_keep), \
            "Did not keep the models that were not in either the reference and the other sequence"
        assert all(model not in sequence for model in expected_remove), \
            "Did not remove the models that were in the reference but were not in the other sequence"
        assert all(model in sequence for model in expected_add), \
            "Did not add the models that were not in the reference but were in the other sequence"

        # given sequences remain unchanged
        assert other == other_original
        assert reference == reference_original

    def test_remove(self, model: ResourceModel, models: list[ResourceModel]):
        sequence = MutableUniqueSequence(models)
        assert model in sequence

        sequence.remove(model)
        assert model not in sequence._items
        assert all(key not in sequence._items_mapped for key in model.unique_keys)

    def test_clear(self, models: list[ResourceModel]):
        initial = models[3:]
        sequence = MutableUniqueSequence(initial)
        assert sequence._items
        assert sequence._items_mapped

        sequence.clear()
        assert not sequence._items
        assert not sequence._items_mapped
