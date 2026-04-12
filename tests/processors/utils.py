import string
from pathlib import Path
from random import randrange, choice
from typing import ClassVar

from mytunes._models import ResourceModel, makecls
from mytunes._models.collection import CollectionModel
from mytunes._models.collection.playlist import Playlist
from mytunes._models.item.album import Album
from mytunes._models.item.artist import Artist
from mytunes._models.properties.name import HasName


class MockCollection(CollectionModel, ResourceModel, HasName, metaclass=makecls()):
    type: ClassVar[str] = choice((
        Album.type,
        Artist.type,
        Playlist.type,
    ))

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
