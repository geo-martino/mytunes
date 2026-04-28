import string
from pathlib import Path
from random import randrange, choice
from typing import ClassVar

from mytunes._base import make_cls
from mytunes._base.resource import ResourceModel
from mytunes.core._collection import CollectionModel
from mytunes.core.properties.name import HasName
from tests.remote import URI_TYPES


class MockCollection(CollectionModel, ResourceModel, HasName, metaclass=make_cls()):
    type: ClassVar[str] = choice(URI_TYPES)

    all_items: list = []

    @property
    def _items(self) -> list:
        return self.all_items


def create_random_file(path: Path, size: int | None = None) -> None:
    """Generates a random file of a given ``size`` in bytes in the test cache folder."""
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w") as file:
        for _ in range(0, size or randrange(int(6*10e3), int(10e6))):
            file.write(choice(string.ascii_letters))
