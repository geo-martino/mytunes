from datetime import date
from io import BytesIO
from pathlib import Path
from random import choice
from typing import get_args

import mutagen.flac
import mutagen.id3
import pytest
from PIL import Image
from faker import Faker

from musify.local.item.track.flac import FLAC
from musify.model import MusifyModel
from musify.model.properties.uri import URI
from tests.local.item.track.testers import LocalTrackTester, LocalTrackEmbeddedImageTester


@pytest.fixture
def pictures(images: list[bytes], image_types: set[str]) -> dict[str, mutagen.flac.Picture]:
    pictures = {}

    for img in images:
        image_type = image_types.pop()

        picture = mutagen.flac.Picture()
        picture.data = img
        picture.type = getattr(mutagen.id3.PictureType, image_type)
        pictures[image_type] = picture

    return pictures


@pytest.fixture
def file(pictures: dict[str, mutagen.flac.Picture], faker: Faker, tmp_path: Path) -> mutagen.flac.FLAC:
    path = tmp_path.joinpath(faker.file_name(category="audio"))

    file = mutagen.flac.FLAC()
    file.filename = str(path)
    file.tags = {"name": "Track title"}
    file.metadata_blocks = [p for p in pictures.values()]

    return file


class TestFLACEmbeddedImage(LocalTrackEmbeddedImageTester):
    @pytest.fixture
    def model(self, images: list[bytes], image_types: set[str], faker: Faker) -> MusifyModel:
        img = Image.open(BytesIO(choice(images)))
        return FLAC.EmbeddedImage(
            path=faker.file_path(category="image"),
            type=choice(list(image_types)),
            mime=img.get_format_mimetype(),
            height=img.height,
            width=img.width,
        )

    def test_get_bytes(self, pictures: dict[str, mutagen.flac.Picture]):
        kind, attr = choice(list(pictures.items()))
        result = FLAC.EmbeddedImage._get_bytes(choice([attr, attr.data]))
        assert result is attr.data

    async def test_get_tag_value(self, model: FLAC.EmbeddedImage, file: mutagen.flac.FLAC):
        file.filename = str(model.path)
        assert (await model._get_tag_value(file)).type == model.id3_type


class TestFLAC(LocalTrackTester):
    @pytest.fixture
    def model(self, uri: URI, faker: Faker, tmp_path: Path) -> MusifyModel:
        extension = choice(get_args(FLAC.model_fields["format"].annotation))
        path = Path(tmp_path, faker.file_name(extension=extension)).absolute()
        return FLAC(name=faker.sentence(), uri=uri, path=path)

    # noinspection PyCallingNonCallable
    def test_extract_tags_from_mutagen(self, file: mutagen.flac.FLAC, faker: Faker):
        tags = faker.pydict()
        file.tags = tags
        assert file.filename
        assert file.pictures

        assert FLAC._extract_tags_from_mutagen(tags) is tags
        assert FLAC._extract_tags_from_mutagen(file.filename) is file.filename

        result = FLAC._extract_tags_from_mutagen(file)
        assert result == tags | dict(images=file.pictures, path=file.filename)

    # noinspection PyCallingNonCallable
    def test_merge_position_values(self):
        tags = {
            "title": ["Sleepwalk My Life Away"],
            "artist": ["Metallica"],
            "album": ["72 Seasons"],
            "album artist": ["Metallica"],
            "track": 3,
            "tracknumber": 5,
            "tracktotal": 10,
            "discnumber": 2,
            "disctotal": 5,
        }
        result = FLAC._merge_position_values(tags)

        assert sum(key.startswith("track") for key in result) == 1
        assert result["tracknumber"] == (3, 10)

        assert sum(key.startswith("disc") for key in result) == 1
        assert result["discnumber"] == (2, 5)

    def test_from_tags(self, model: FLAC, images: list[bytes], pictures: dict[str, mutagen.flac.Picture], faker: Faker):
        sep = choice(FLAC._tag_sep)
        tags = {
            "title": ["Sleepwalk My Life Away"],
            "artist": ["Metallica"],
            "album": ["72 Seasons"],
            "album artist": ["Metallica"],
            "genre": ["Hard Rock", "Metal" + sep + "Rock", "Thrash Metal"],
            choice(("tracknumber", "tracktotal")): ["04"],
            "discnumber": ["1"],
            "disctotal": ["2"],
            "bpm": ["124.931"],
            "key": ["B"],
            choice(("date", "year")): ["2023-04-14"],
            choice(("comment", "description")): ["spotify:track:1WjgFpSxwA0Bqyr7hWc3f1"],
            "compilation": ["0"],
            "images": list(pictures.values()),
        }

        model = FLAC(**tags, path=model.path)
        assert model.name == "Sleepwalk My Life Away"
        assert model.artist == "Metallica"
        assert model.album.name == "72 Seasons"
        assert [genre.name for genre in model.genres] == ["Hard Rock", "Metal", "Rock", "Thrash Metal"]
        assert model.track.number == 4
        assert model.track.total is None
        assert model.disc.number == 1
        assert model.disc.total == 2
        assert model.bpm == 124.931
        assert model.key.key == "B"
        assert model.released_at == date(2023, 4, 14)
        assert model.comments == ["spotify:track:1WjgFpSxwA0Bqyr7hWc3f1"]
        assert model.images == {kind: FLAC.EmbeddedImage.model_validate(attr) for kind, attr in pictures.items()}
