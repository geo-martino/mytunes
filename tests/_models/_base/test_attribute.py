from typing import Annotated

import pytest
from pydantic import computed_field

from mytunes._models import AttributeModel
from mytunes._models.metadata import Attribute
from mytunes.exception import MyTunesAttributeError
from tests.testers import BaseModelTester


class ModelCode(AttributeModel):
    code: Annotated[str | None, Attribute()] = None
    width: int | None = None

    @computed_field
    @property
    def is_set(self) -> Annotated[bool, Attribute()]:
        return self.code is not None and self.width is not None


class ModelPosition(AttributeModel):
    number: Annotated[int, Attribute()]
    total: int
    extra: Annotated[ModelCode, Attribute()]

    @property
    def is_first(self) -> bool:
        return self.number == 1

    @property
    def is_last(self) -> bool:
        return self.number == self.total


class ModelTrack(AttributeModel):
    name: Annotated[str, Attribute()]
    track: Annotated[int | ModelPosition, Attribute()]
    extra: Annotated[ModelCode | None, Attribute()]
    other: float

    @property
    def is_single(self) -> bool:
        return self.track == 1


class ModelAttributes(AttributeModel):
    name: Annotated[str, Attribute()] = "name"
    track: Annotated[int, Attribute()] = 2
    extra: Annotated[dict, Attribute()] = {}
    other: Annotated[float, Attribute()] = 1.0

    @property
    def include_me(self) -> Annotated[bool, Attribute()]:
        return True

    @computed_field
    @property
    def do_not_include_me(self) -> bool:
        return True

    @property
    def do_not_include_me_either(self) -> bool:
        return True


class TestAttributeModel(BaseModelTester):

    @pytest.fixture
    def model(self) -> ModelTrack:
        return ModelTrack(
            name="Test",
            track=ModelPosition(
                number=1,
                total=10,
                extra=ModelCode(
                    code="B123",
                    width=200,
                ),
            ),
            extra=ModelCode(
                code="E456",
                width=300,
            ),
            other=3.14,
        )

    def test_get_tag_attribute_names(self):
        assert ModelAttributes.__tag_attributes__ == {
            "name",
            "other",
            "extra",
            "track",
            "include_me",
        }

        assert ModelTrack.__tag_attributes__ == {
            "name",
            "track",
            "track.number",
            "track.extra",
            "track.extra.code",
            "track.extra.is_set",
            "extra",
            "extra.code",
            "extra.is_set",
        }

    def test_get_tag_attribute_names_includes_parent_attributes(self):
        class ModelAlbum(ModelPosition, ModelCode):
            title: Annotated[str, Attribute()]
            artist: Annotated[str, Attribute()]

        assert ModelAlbum.__tag_attributes__ == {
            "title",
            "artist",
            "number",
            "is_set",
            "extra",
            "extra.code",
            "extra.is_set",
            "code",
        }

    def test_get_attribute_value(self, model: ModelTrack):
        assert getattr(model, "name") == model.name
        assert getattr(model, "track") == model.track
        assert getattr(model, "track.number") == model.track.number
        assert getattr(model, "track.extra.code") == model.track.extra.code
        assert getattr(model, "extra.width") == model.extra.width

    def test_get_attribute_value_when_parent_is_none(self, model: ModelTrack):
        model.extra = None
        assert getattr(model, "extra.code") is None

    def test_set_attribute_value(self, model: ModelTrack):
        setattr(model, "name", "New Name")
        setattr(model, "track.number", 42)
        setattr(model, "track.extra.code", "NEWCODE")
        setattr(model, "extra.code", "EXTRACODE")

        assert model.name == "New Name"
        assert model.track.number == 42
        assert model.track.extra.code == "NEWCODE"
        assert model.extra.code == "EXTRACODE"

    def test_set_attribute_value_when_parent_is_none(self, model: ModelTrack):
        model.extra = None
        with pytest.raises(MyTunesAttributeError):
            setattr(model, "extra.code", "EXTRACODE")
