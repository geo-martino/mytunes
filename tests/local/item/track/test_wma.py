import struct
from datetime import date
from io import BytesIO
from pathlib import Path
from random import choice
from typing import get_args

import mutagen.id3
import pytest
from PIL import Image
from faker import Faker
# noinspection PyProtectedMember
from mutagen.asf import ASFUnicodeAttribute, ASFByteArrayAttribute

from musify.local.item.track.wma import WMA
from musify.model import MusifyModel
from musify.model.properties.image import PICTURE_TYPES, get_picture_name_from_id3_value
from musify.model.properties.uri import URI
from tests.model.testers import UniqueKeyTester
from tests.utils import assert_validator_skips


class TestWMA(UniqueKeyTester):
    @pytest.fixture
    def model(self, uri: URI, faker: Faker, tmp_path: Path) -> MusifyModel:
        extension = choice(get_args(WMA.model_fields["format"].annotation))
        path = Path(tmp_path, faker.file_name(extension=extension)).absolute()
        return WMA(name=faker.sentence(), uri=uri, path=path)

    @pytest.fixture
    def pictures(self, images: list[bytes]) -> dict[int, ASFByteArrayAttribute]:
        pictures = {}
        types = set(PICTURE_TYPES.values())
        for img in images:
            fmt = Image.open(BytesIO(img)).format
            kind = types.pop()

            header = struct.pack("<bi", kind, len(img))
            header += Image.MIME[fmt].encode("utf-16") + b"\x00\x00"  # mime
            header += "".encode("utf-16") + b"\x00\x00"  # description

            pictures[kind] = ASFByteArrayAttribute(header + img)

        return pictures

    def test_deserialize_unicode_attribute(self, faker: Faker):
        expected = faker.sentence()
        attribute = ASFUnicodeAttribute(expected)
        assert WMA._deserialize_unicode_attribute(attribute) == expected

    def test_deserialize_unicode_attributes(self, faker: Faker):
        expected = [faker.sentence() for _ in range(faker.random_int(3, 6))]
        attributes = [ASFUnicodeAttribute(item) for item in expected]
        assert WMA._deserialize_unicode_attributes(attributes) == expected

    def test_deserialize_images_from_wma_attributes(
            self, images: list[bytes], pictures: dict[int, ASFByteArrayAttribute]
    ):
        pictures = {kind: choice([pic, pic.value]) for kind, pic in pictures.items()}
        kind, picture = next(iter(pictures.items()))
        assert WMA._deserialize_images_from_wma_attributes(picture) == {kind: images[0]}
        assert WMA._deserialize_images_from_wma_attributes(list(pictures.values())) == dict(zip(pictures, images))

    def test_deserialize_images_from_wma_attributes_skips(self, faker: Faker):
        assert_validator_skips(WMA._deserialize_images_from_wma_attributes, None)
        assert_validator_skips(WMA._deserialize_images_from_wma_attributes, faker.pyint())
        assert_validator_skips(WMA._deserialize_images_from_wma_attributes, faker.pytuple())
        assert_validator_skips(WMA._deserialize_images_from_wma_attributes, faker.pylist())
        assert_validator_skips(WMA._deserialize_images_from_wma_attributes, faker.pydict())

    def test_from_tags(self, model: WMA, images: list[bytes], pictures: dict[int, ASFByteArrayAttribute], faker: Faker):
        sep = choice(WMA._tag_sep)
        tags = {
            "Title": [ASFUnicodeAttribute("Sleepwalk My Life Away")],
            "Author": [ASFUnicodeAttribute("Metallica")],
            "WM/AlbumTitle": [ASFUnicodeAttribute("72 Seasons")],
            "WM/AlbumArtist": [ASFUnicodeAttribute("Metallica")],
            "WM/Genre": [
                ASFUnicodeAttribute("Hard Rock"),
                ASFUnicodeAttribute("Metal" + sep + "Rock"),
                ASFUnicodeAttribute("Thrash Metal")
            ],
            choice(("WM/TrackNumber", "TotalTracks")): [ASFUnicodeAttribute("04")],
            "WM/PartOfSet": [ASFUnicodeAttribute("1/2")],
            "WM/BeatsPerMinute": [ASFUnicodeAttribute("124.931")],
            "WM/InitialKey": [ASFUnicodeAttribute("B")],
            choice(("WM/Year", "WM/OriginalReleaseYear")): [ASFUnicodeAttribute("2023-04-14")],
            choice(("Description", "WM/Comments")): [ASFUnicodeAttribute("spotify:track:1WjgFpSxwA0Bqyr7hWc3f1")],
            "WM/Picture": list(pictures.values()),
            "COMPILATION": [ASFUnicodeAttribute("0")],
        }

        model = WMA(**tags, path=model.path)
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

        expected_images = {
            get_picture_name_from_id3_value(kind): Image.open(BytesIO(img))
            for kind, img in zip(pictures, images)
        }
        assert model.images == expected_images
