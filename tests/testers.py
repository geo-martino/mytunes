## DEPRECATED

import json
import re
from abc import ABCMeta, abstractmethod
from collections.abc import Container

import pytest

from musify.field import Fields, TagField, ALL_FIELDS, Field, TagFields
from musify.models import MusifyObject, MusifyResource
from musify.printer import PrettyPrinter
from musify.types import MusifyEnum


###########################################################################
## Printer
###########################################################################
class PrettyPrinterTester(metaclass=ABCMeta):
    """Run generic tests for :py:class:`PrettyPrinter` implementations"""
    dict_json_equal: bool = True

    @abstractmethod
    def obj(self, *args, **kwargs) -> PrettyPrinter:
        """Yields a :py:class:`PrettyPrinter` object to be tested as pytest.fixture."""
        raise NotImplementedError

    @staticmethod
    def test_dict(obj: PrettyPrinter):
        # check dict output and str+repr dunder methods that use this output
        obj_dict = obj.as_dict()
        name = obj.__class__.__name__

        assert re.match(rf"^{name}\([\s\S]*\)$", str(obj))
        # plus 2 for class name line and final closing bracket line
        assert len(str(obj).split("\n")) >= len(obj_dict) + (2 if "\n" in str(obj) else 0)
        assert repr(obj) == f"{name}({obj_dict})"

    def test_json(self, obj: PrettyPrinter):
        obj_dict = obj.as_dict()
        obj_json = obj.json()

        if self.dict_json_equal:
            assert len(obj_dict) == len(obj_json)
            assert obj_dict.keys() == obj_json.keys()

        # check JSON is serializable
        assert isinstance(json.dumps(obj_json), str)


###########################################################################
## Enum
###########################################################################
class EnumTester(metaclass=ABCMeta):
    """Run generic tests for :py:class:`MusifyEnum` implementations"""

    @property
    @abstractmethod
    def cls(self) -> type[MusifyEnum]:
        """The :py:class:`MusifyEnum` class to test"""
        raise NotImplementedError

    def test_gets_enum_from_name_and_value(self):
        all_enums = self.cls.all()
        for enum in all_enums:
            assert enum == self.cls.from_name(enum.name)[0]
            assert enum == self.cls.from_value(enum.value)[0]

        assert self.cls.from_name(*(enum.name for enum in all_enums)) == set(all_enums)
        assert self.cls.from_value(*all_enums, fail_on_many=False) == set(all_enums)


###########################################################################
## Field
###########################################################################
class FieldTester(EnumTester, metaclass=ABCMeta):
    """Run generic tests for :py:class:`Field` enum implementations"""

    @abstractmethod
    def reference_cls(self) -> type[MusifyObject]:
        """The associated class to validate field names against."""
        raise NotImplementedError

    @abstractmethod
    def reference_ignore(self) -> type[MusifyObject]:
        """The associated class to validate field names against."""
        raise NotImplementedError

    def test_gets_enum_from_name_and_value(self):
        all_enums = self.cls.all()
        for enum in all_enums:
            assert self.cls.map(enum) == self.cls.from_name(enum.name)
            assert self.cls.map(enum) == self.cls.from_value(enum.value)

        all_mapped_enums = {e for enum in all_enums for e in self.cls.map(enum)}
        assert set(self.cls.from_name(*(enum.name for enum in all_enums))) == all_mapped_enums
        assert set(self.cls.from_value(*all_enums)) == all_mapped_enums

    def test_values_match(self):
        all_field_names = [enum.name for enum in ALL_FIELDS]
        for enum in self.cls.all():
            if enum.name not in all_field_names:  # not a combined field enum
                continue
            enum_combined = Fields.from_name(enum.name)
            assert len(enum_combined) == 1
            assert enum.value == enum_combined[0]

    def test_all_fields_are_valid(self, reference_cls: type[MusifyObject], reference_ignore: Container[Field]):
        names = [e.name.lower() for enum in self.cls.all() if enum not in reference_ignore for e in self.cls.map(enum)]

        for name in names:
            assert name in dir(reference_cls)
            assert isinstance(getattr(reference_cls, name), property)


class TagFieldTester(FieldTester, metaclass=ABCMeta):
    """Run generic tests for :py:class:`TagField` enum implementations"""

    @property
    @abstractmethod
    def cls(self) -> type[TagField]:
        """The :py:class:`TagField` class to test"""
        raise NotImplementedError

    def test_tag_field_gives_valid_tags(self):
        all_fields = self.cls.all()
        all_tags = [tag for enum in all_fields for tag in enum.to_tag()]

        assert all(tag in self.cls.__tags__ for tag in all_tags)
        assert all(tag in self.cls.__tags__ for tag in self.cls.to_tags(all_fields))


###########################################################################
## Base
###########################################################################
class MusifyItemTester(PrettyPrinterTester, metaclass=ABCMeta):
    """Run generic tests for :py:class:`MusifyItem` implementations"""

    @abstractmethod
    def item(self, *args, **kwargs) -> MusifyResource:
        """Yields an :py:class:`MusifyItem` object to be tested as pytest.fixture."""
        raise NotImplementedError

    @abstractmethod
    def item_unequal(self, *args, **kwargs) -> MusifyResource:
        """Yields an :py:class:`MusifyItem` object that is does not equal the ``item`` being tested"""
        raise NotImplementedError

    @abstractmethod
    def item_modified(self, *args, **kwargs) -> MusifyResource:
        """
        Yields an :py:class:`MusifyItem` object that is equal to the ``item``
        being tested with some modified values
        """
        raise NotImplementedError

    @pytest.fixture
    def obj(self, item: MusifyResource) -> PrettyPrinter:
        return item

    @staticmethod
    def test_equality(item: MusifyResource, item_modified: MusifyResource, item_unequal: MusifyResource):
        assert hash(item) == hash(item)
        assert item == item

        assert hash(item) == hash(item_modified)
        assert item == item_modified

        assert hash(item) != hash(item_unequal)
        assert item != item_unequal

    @staticmethod
    def test_getitem_dunder_method(item: MusifyResource):
        assert item["name"] == item.name
        assert item["uri"] == item.uri
        assert item[TagFields.NAME] == item.name
        assert item[TagFields.URI] == item.uri
