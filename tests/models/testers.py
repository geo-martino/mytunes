from abc import ABCMeta, abstractmethod
from collections.abc import Hashable

import pytest
from pydantic import TypeAdapter

from musify.models import MusifyModel, MusifyResource


class MusifyModelTester(metaclass=ABCMeta):
    """Generic base class for testing :py:class:`.MusifyModel` implementations"""
    @abstractmethod
    def model(self, **kwargs) -> MusifyModel:
        """Fixture for the models to test"""
        raise NotImplementedError

    @pytest.fixture
    def adapter(self, model: MusifyModel) -> TypeAdapter:
        """Fixture for the type adapter to use when validating python objects for this models"""
        return TypeAdapter(model.__class__)

    @staticmethod
    def test_model_registry(model: MusifyResource):
        if model.__class__.__final__:
            assert model.__class__ in MusifyModel.registered_submodels
        else:
            assert model.__class__ not in MusifyModel.registered_submodels


class MusifyResourceTester(MusifyModelTester, metaclass=ABCMeta):
    """Generic base class for testing :py:class:`.MusifyResource` implementations"""

    def test_check_unique_key_tester_enabled(self, model: MusifyResource):
        """Test that the unique key tester is enabled"""
        if model.__unique_attributes__:
            assert isinstance(self, UniqueKeyTester), "Unique keys are configured but UniqueKeyTester is not enabled"
        else:
            assert not isinstance(self, UniqueKeyTester), \
                "Unique keys are not configured but UniqueKeyTester is enabled"

    @staticmethod
    def test_check_unique_keys(model: MusifyResource):
        """Test that the unique keys are set correctly"""
        assert not model.__unique_attributes__, "Unique attributes are not set on the test models"
        assert model.unique_keys == {id(model)}, "ID not found in unique keys"


class UniqueKeyTester(MusifyModelTester, metaclass=ABCMeta):
    """Generic base class for testing :py:class:`.MusifyResource` implementations with unique keys set"""
    @staticmethod
    def test_check_unique_keys(model: MusifyResource):
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
