import pytest
from faker import Faker

from musify.models import MusifyModel
from musify.models.properties.music import KeySignature
from tests.models.testers import MusifyModelTester


class TestKeySignature(MusifyModelTester):
    @pytest.fixture
    def model(self, faker: Faker) -> MusifyModel:
        # noinspection PyProtectedMember
        return KeySignature(
            root=faker.random_int(min=0, max=len(KeySignature._root_notes) - 1),
            mode=faker.boolean(),
        )

    def test_from_key(self, model: KeySignature) -> None:
        model = model.model_validate("F")
        assert model.root == 5
        assert model.mode == 0
        assert model.key == "F"

        model = model.model_validate("Fm")
        assert model.root == 5
        assert model.mode == 1
        assert model.key == "Fm"

    def test_from_key_with_sharp_or_flat(self, model: KeySignature) -> None:
        model = model.model_validate("F#")
        assert model.root == 6
        assert model.mode == 0
        assert model.key == "F#/Gb"

        model.key = "Bbm"
        assert model.root == 10
        assert model.mode == 1
        assert model.key == "A#/Bbm"

    def test_key_property(self, model: KeySignature) -> None:
        model.root = 5
        model.mode = False
        assert model.key == str(model) == "F"

        model.mode = True
        assert model.key == str(model) == "Fm"

    def test_set_by_key_signature(self, model: KeySignature) -> None:
        model.mode = False
        model.root = "Gm"
        assert model.root == 7
        assert not model.mode  # remains unchanged

        model.mode = "Am"
        assert model.root == 7  # remains unchanged
        assert model.mode

        model.key = "Cm"
        assert model.root == 0
        assert model.mode

    def test_to_string(self, model: KeySignature) -> None:
        assert str(model) == model.key
