from abc import ABCMeta, abstractmethod
from collections.abc import Hashable

import pytest
from pydantic import TypeAdapter

from musify.models import BaseModel, ResourceModel


class BaseModelTester(metaclass=ABCMeta):
    """Generic base class for testing :py:class:`.BaseModel` implementations"""
    @abstractmethod
    def model(self, **kwargs) -> BaseModel:
        """Fixture for the models to test"""
        raise NotImplementedError

    @pytest.fixture
    def adapter(self, model: BaseModel) -> TypeAdapter:
        """Fixture for the type adapter to use when validating python objects for this models"""
        return TypeAdapter(model.__class__)

    def test_check_unique_key_tester_enabled(self, model: ResourceModel):
        """Test that the unique key tester is enabled"""
        if isinstance(model, ResourceModel) and model.__unique_attributes__:
            assert isinstance(self, UniqueKeyTester), "Unique keys are configured but UniqueKeyTester is not enabled"
        else:
            assert not isinstance(self, UniqueKeyTester), \
                "Unique keys are not configured but UniqueKeyTester is enabled"

    @staticmethod
    def test_model_registry(model: BaseModel):
        if model.__class__.__final__:
            assert model.__class__ in BaseModel.registered_submodels
        else:
            assert model.__class__ not in BaseModel.registered_submodels


class NoUniqueKeyTester(BaseModelTester, metaclass=ABCMeta):
    """Generic base class for testing :py:class:`.ResourceModel` implementations"""

    @staticmethod
    def test_check_unique_keys(model: BaseModel):
        """Test that the unique keys are set correctly"""
        if not isinstance(model, ResourceModel):
            return pytest.skip("Model is not a ResourceModel, skipping unique key test")

        assert not model.__unique_attributes__, "Unique attributes are not set on the test models"
        assert model.unique_keys == {id(model)}, "ID not found in unique keys"


class UniqueKeyTester(BaseModelTester, metaclass=ABCMeta):
    """Generic base class for testing :py:class:`.ResourceModel` implementations with unique keys set"""
    @staticmethod
    def test_check_unique_keys(model: ResourceModel):
        """Test that the unique keys are set correctly"""
        assert model.__unique_attributes__, "Unique attributes are not set on the test models"
        assert len(model.unique_keys) > 1, "Unique keys not found"

        for key in model.__unique_attributes__:
            if (value := getattr(model, key, None)) is None:
                assert None not in model.unique_keys, "Unique keys should not contain None"
                continue

            assert value in model.unique_keys, f"Value {value} not found in unique keys"
            assert isinstance(value, Hashable)

            try:
                setattr(model, key, None)
                assert value not in model.unique_keys, f"Value {value} should not be in unique keys after removing it"
            except (AttributeError, ValueError):  # value is not mutable or nullable
                pass
