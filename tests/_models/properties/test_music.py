import pytest
from faker import Faker

from mytunes._models.properties.music import KeySignature
from tests.testers import BaseModelTester


class TestKeySignature(BaseModelTester):
    @pytest.fixture
    def model(self, faker: Faker) -> KeySignature:
        return KeySignature(
            root=faker.random_int(0, len(KeySignature._root_notes) - 1),
            mode=faker.random_int(0, 1),
        )

    def test_from_key(self, model: KeySignature):
        model = model.model_validate("F")
        assert model.root == 5
        assert model.mode == 0
        assert model.key == "F"

        model = model.model_validate("Fm")
        assert model.root == 5
        assert model.mode == 1
        assert model.key == "Fm"

    def test_from_key_with_sharp_or_flat(self):
        model = KeySignature.model_validate("F#")
        assert model.root == 6
        assert model.mode == 0
        assert model.key == "F#/Gb"

        model = KeySignature.model_validate("Bbm")
        assert model.root == 10
        assert model.mode == 1
        assert model.key == "A#m/Bbm"

        model = KeySignature.model_validate("G#m/Abm")
        assert model.root == 8
        assert model.mode == 1
        assert model.key == "G#m/Abm"

    def test_key_property(self, model: KeySignature):
        model = KeySignature(root=5, mode=0)
        assert model.key == str(model) == "F"

        model = KeySignature(root=5, mode=1)
        assert model.key == str(model) == "Fm"

    def test_to_string(self, model: KeySignature):
        assert str(model) == model.key
