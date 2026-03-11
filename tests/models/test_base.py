from typing import final, ClassVar

import pytest
from pydantic import Field

from musify.exception import MusifyAttributeError
from musify.models import BaseModel


@final
class FinalModel(BaseModel):
    __final__ = True


class TestBaseModel:

    def test_final_model_registration(self):
        """Test that final models are registered in the model registry"""
        assert FinalModel in BaseModel.__model_registry__
        assert FinalModel in BaseModel.registered_submodels

    class ParentWithClassVars(BaseModel):
        var1: ClassVar[str] = "value1"
        var2: ClassVar[str] = Field(description="Unset var2")
        var3: ClassVar[int]

    def test_validate_class_vars_not_set_on_final_model(self):
        with pytest.raises(MusifyAttributeError):
            @final
            class Child(self.ParentWithClassVars):
                __final__ = True

        with pytest.raises(MusifyAttributeError):
            @final
            class Child(self.ParentWithClassVars):  # var2 is still not set
                __final__ = True
                var3 = 42

    def test_validate_class_vars_are_set_on_final_model(self):
        @final
        class Child(self.ParentWithClassVars):
            __final__ = True
            var2 = "value2"
            var3 = 42

    def test_validate_class_vars_skips_on_non_final_model(self):
        class Child(self.ParentWithClassVars):
            pass
