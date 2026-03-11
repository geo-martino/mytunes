import pytest

from musify.exception import MusifyAttributeError
from musify.models import AttributeModel
from tests.models.testers import BaseModelTester


class ModelCode(AttributeModel):
    __tag_attributes__ = ("code",)

    code: str | None = None
    width: int | None = None

    @property
    def is_set(self) -> bool:
        return self.code is not None and self.width is not None


class ModelPosition(AttributeModel):
    __tag_attributes__ = ("number", "extra")

    number: int
    total: int
    extra: ModelCode

    @property
    def is_first(self) -> bool:
        return self.number == 1

    @property
    def is_last(self) -> bool:
        return self.number == self.total


class ModelTrack(AttributeModel):
    __tag_attributes__ = ("name", "track", "extra")

    name: str
    track: int | ModelPosition
    extra: ModelCode | None
    other: float

    @property
    def is_single(self) -> bool:
        return self.track == 1


class ModelAttributes(AttributeModel):
    __include_fields__ = False
    __include_attributes__ = False

    name: str = "name"
    track: int = 2
    extra: dict = {}
    other: float = 1.0


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

    def test_get_tag_fields(self):
        assert getattr(ModelTrack, "name") is ModelTrack.model_fields["name"]
        assert getattr(ModelTrack, "track") is ModelTrack.model_fields["track"]
        assert getattr(ModelTrack, "track.number") is ModelPosition.model_fields["number"]
        assert getattr(ModelTrack, "track.extra.code") == ModelCode.model_fields["code"]
        assert getattr(ModelTrack, "extra.width") == ModelCode.model_fields["width"]

    def test_get_tag_properties(self):
        assert getattr(ModelTrack, "is_single") == ModelTrack.is_single
        assert getattr(ModelTrack, "track.is_first") == ModelPosition.is_first
        assert getattr(ModelTrack, "track.is_last") == ModelPosition.is_last
        assert getattr(ModelTrack, "track.extra.is_set") == ModelCode.is_set
        assert getattr(ModelTrack, "extra.is_set") == ModelCode.is_set

    def test_get_tag_attribute_names(self):
        assert ModelTrack.__tag_attributes__ == (
            "name",
            "track",
            "track.number",
            "track.extra",
            "track.extra.code",
            "extra",
            "extra.code",
        )

    def test_get_tag_attribute_names_includes_parent_attributes(self):
        class ModelAlbum(ModelPosition, ModelCode):
            __tag_attributes__ = ("title", "artist")

            title: str
            artist: str

        assert ModelAlbum.__tag_attributes__ == (
            "title",
            "number",
            "extra",
            "extra.code",
            "code",
            "artist",
        )

    def test_get_attribute_value(self, model: ModelTrack):
        assert getattr(model, "name") == model.name
        assert getattr(model, "track") == model.track
        assert getattr(model, "track.number") == model.track.number
        assert getattr(model, "track.extra.code") == model.track.extra.code
        assert getattr(model, "extra.width") == model.extra.width

    def test_get_attribute_value_when_parent_is_none(self, model: ModelTrack):
        model.extra = None
        assert getattr(model, "extra") is None

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
        with pytest.raises(MusifyAttributeError):
            setattr(model, "extra.code", "EXTRACODE")

    def test_sets_tag_attributes_no_properties(self):
        class ModelAttributesTest(ModelAttributes):
            __include_fields__ = True
            __include_properties__ = False

            @property
            def computed_property(self) -> str:
                return "computed"

        assert ModelAttributesTest.__tag_attributes__ == (
            "name",
            "track",
            "extra",
            "other",
        )

    def test_sets_tag_attributes_no_fields(self):
        class ModelAttributesTest(ModelAttributes):
            __include_fields__ = False
            __include_properties__ = True

            @property
            def computed_property(self) -> str:
                return "computed"

        assert ModelAttributesTest.__tag_attributes__ == ("computed_property",)
