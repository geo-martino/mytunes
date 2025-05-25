from datetime import date
from io import BytesIO
from pathlib import Path
from random import choice
from typing import get_args, Any

import mutagen.id3
import pytest
from PIL import Image
from faker import Faker
from mutagen.mp4 import MP4FreeForm, MP4Cover

from musify.local.item.track.m4a import M4A
from musify.model import MusifyModel
from musify.model.properties.uri import URI
from tests.local.item.track.testers import LocalTrackTester, LocalTrackEmbeddedImageTester


@pytest.fixture
def pictures(images: list[bytes], image_types: set[str]) -> dict[str, mutagen.mp4.MP4Cover]:
    # AFAIK, MP4 only supports a single image per track so we just check for a single image type
    return {"COVER_FRONT": mutagen.mp4.MP4Cover(choice(images))}


class TestM4AEmbeddedImage(LocalTrackEmbeddedImageTester):
    @pytest.fixture
    def model(self, images: list[bytes], image_types: set[str], faker: Faker) -> MusifyModel:
        img = Image.open(BytesIO(choice(images)))
        return M4A.EmbeddedImage(
            path=faker.file_path(category="image"),
            type=choice(list(image_types)),
            mime=img.get_format_mimetype(),
            height=img.height,
            width=img.width,
        )

    def test_get_bytes(self, pictures: dict[str, mutagen.mp4.MP4Cover]):
        kind, attr = choice(list(pictures.items()))
        result = M4A.EmbeddedImage._get_bytes(choice([attr, bytes(attr)]))
        assert result == bytes(attr)


class TestM4A(LocalTrackTester):
    @pytest.fixture
    def model(self, uri: URI, faker: Faker, tmp_path: Path) -> MusifyModel:
        extension = choice(get_args(M4A.model_fields["format"].annotation))
        path = Path(tmp_path, faker.file_name(extension=extension)).absolute()
        return M4A(name=faker.sentence(), uri=uri, path=path)

    def test_deserialize_free_form_field(self, faker: Faker):
        expected = faker.pystr()
        field = MP4FreeForm(expected.encode())
        assert M4A._deserialize_free_form_field(field) == expected

    def test_deserialize_free_form_fields(self, faker: Faker):
        expected = [faker.sentence() for _ in range(faker.random_int(3, 6))]
        attributes = [MP4FreeForm(item.encode()) for item in expected]
        assert M4A._deserialize_free_form_fields(attributes) == expected

    def test_from_tags(self, model: M4A, images: list[bytes], pictures: dict[str, mutagen.mp4.MP4Cover], faker: Faker):
        sep = choice(M4A._tag_sep)
        tags = {
            "©nam": ["Sleepwalk My Life Away"],
            "©ART": ["Metallica"],
            "©alb": ["72 Seasons"],
            "aART": ["Metallica"],
            choice(("----:com.apple.iTunes:GENRE", "©gen", "gnre")): [
                MP4FreeForm(b"Hard Rock"),
                MP4FreeForm(f"Metal{sep}Rock".encode()),
                MP4FreeForm(b"Thrash Metal")
            ],
            "trkn": [4],
            "disk": [(1, 2)],
            "tmpo": [124],
            "----:com.apple.iTunes:INITIALKEY": [MP4FreeForm(b"B")],
            "©day": ["2023-04-14"],
            "©cmt": ["spotify:track:1WjgFpSxwA0Bqyr7hWc3f1"],
            "covr": list(map(MP4Cover, images)),
            "cpil": True,
        }

        model = M4A(**tags, path=model.path)
        assert model.name == "Sleepwalk My Life Away"
        assert model.artist == "Metallica"
        assert model.album.name == "72 Seasons"
        assert [genre.name for genre in model.genres] == ["Hard Rock", "Metal", "Rock", "Thrash Metal"]
        assert model.track.number == 4
        assert model.track.total is None
        assert model.disc.number == 1
        assert model.disc.total == 2
        assert model.bpm == 124
        assert model.key.key == "B"
        assert model.released_at == date(2023, 4, 14)
        assert model.comments == ["spotify:track:1WjgFpSxwA0Bqyr7hWc3f1"]
        assert model.images == {kind: M4A.EmbeddedImage.model_validate(attr) for kind, attr in pictures.items()}
