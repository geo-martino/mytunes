from copy import deepcopy
from typing import final, ClassVar

import pytest
from pydantic import Field, AliasChoices

from mytunes._models import BaseModel
from mytunes._models.exception import ModelError
from mytunes.exception import MyTunesImportError


@final
class FinalModel(BaseModel):
    __final__ = True


class TestFinalModel:

    def test_final_model_registration(self):
        """Test that final models are registered in the model registry"""
        assert FinalModel in BaseModel.__model_registry__
        assert FinalModel in BaseModel.registered_submodels

    class ParentWithClassVars(BaseModel):
        var1: ClassVar[str] = "value1"
        var2: ClassVar[str] = Field(description="Unset var2")
        var3: ClassVar[int]

    # noinspection PyUnusedLocal
    def test_validate_class_vars_not_set_on_final_model(self):
        with pytest.raises(ModelError):
            @final
            class Child(self.ParentWithClassVars):
                __final__ = True

        with pytest.raises(ModelError):
            @final
            class Child(self.ParentWithClassVars):  # var2 is still not set
                __final__ = True
                var3 = 42

    # noinspection PyUnusedLocal
    def test_validate_class_vars_are_set_on_final_model(self):
        @final
        class Child(self.ParentWithClassVars):
            __final__ = True
            var2 = "value2"
            var3 = 42

    # noinspection PyUnusedLocal
    def test_validate_class_vars_skips_on_non_final_model(self):
        class Child(self.ParentWithClassVars):  # just check this doesn't fail
            pass


class TestBaseModel:
    class TestModel(BaseModel):
        field1: str = Field(
            alias="alias1",
            validation_alias="valid1",
            serialization_alias="serial1",
        )
        field2: int = Field(
            validation_alias=AliasChoices("choice1", "choice2"),
        )
        field3: int = Field(
            serialization_alias="serial1",
        )

    def test_required_modules_installed(self):
        class TestModelWithNoModules(BaseModel):
            __required_modules__ = {"nonexistent_module": None}
            field: str

        assert not TestModelWithNoModules.required_modules_installed

        with pytest.raises(MyTunesImportError):
            TestModelWithNoModules(field="test")

    def test_get_aliases_skips_name(self):
        cls = deepcopy(self.TestModel)
        cls.model_config["validate_by_name"] = False

        assert cls._get_aliases("field1") == {"alias1", "valid1"}
        assert cls._get_aliases("field2") == {"choice1", "choice2"}
        assert cls._get_aliases("field3") == {"field3"}

    def test_get_aliases_includes_name(self):
        cls = deepcopy(self.TestModel)
        cls.model_config["validate_by_name"] = True

        assert cls._get_aliases("field1") == {"field1", "alias1", "valid1"}
        assert cls._get_aliases("field2") == {"field2", "choice1", "choice2"}
        assert cls._get_aliases("field3") == {"field3"}

    def test_get_aliases_includes_serialization_alias(self):
        cls = deepcopy(self.TestModel)
        cls.model_config["validate_by_name"] = True

        assert cls._get_aliases("field1", True) == {"field1", "alias1", "valid1", "serial1"}
        assert cls._get_aliases("field2", True) == {"field2", "choice1", "choice2"}
        assert cls._get_aliases("field3", True) == {"field3", "serial1"}

    def test_get_value_from_data(self):
        data = {"alias1": "value", "choice1": 42, "field3": 100}

        assert self.TestModel._get_value_from_data(data, "field1") == "value"
        assert self.TestModel._get_value_from_data(data, "field2") == 42
        assert self.TestModel._get_value_from_data(data, "field3") == 100
