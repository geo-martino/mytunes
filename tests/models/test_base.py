from typing import final

from musify.models import MusifyModel


@final
class FinalModel(MusifyModel):
    __final__ = True


class TestMusifyModel:
    def test_final_model_registration(self):
        """Test that final models are registered in the model registry"""
        assert FinalModel in MusifyModel.__model_registry__
        assert FinalModel in MusifyModel.registered_submodels
