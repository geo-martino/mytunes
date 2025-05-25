import struct
from datetime import date
from io import BytesIO
from pathlib import Path
from random import choice
from typing import get_args
from unittest import mock

import mutagen.id3
import pytest
from PIL import Image
from faker import Faker
# noinspection PyProtectedMember
from mutagen.asf import ASFUnicodeAttribute, ASFByteArrayAttribute

from musify.local.item.track.wma import WMA
from musify.model import MusifyModel
from musify.model.properties.uri import URI
from tests.local.item.track.testers import LocalTrackEmbeddedImageTester, LocalTrackTester
from tests.utils import assert_validator_skips


@pytest.fixture
def pictures(images: list[bytes], image_types: set[str]) -> dict[str, ASFByteArrayAttribute]:
    pictures = {}
    for img in images:
        fmt = Image.open(BytesIO(img)).format
        kind = image_types.pop()

        header = struct.pack("<bi", int(getattr(mutagen.id3.PictureType, kind)), len(img))
        mime = Image.MIME[fmt].encode("utf-16")
        description = "".encode("utf-16")
        data = b"\x00\x00".join((header + mime, description, img))

        pictures[kind] = ASFByteArrayAttribute(data)

    return pictures


class TestWMAEmbeddedImage(LocalTrackEmbeddedImageTester):
    @pytest.fixture
    def model(self, images: list[bytes], image_types: set[str], faker: Faker) -> MusifyModel:
        img = Image.open(BytesIO(choice(images)))
        return WMA.EmbeddedImage(
            path=faker.file_path(category="image"),
            type=choice(list(image_types)),
            mime=img.get_format_mimetype(),
            height=img.height,
            width=img.width,
        )

    def test_unpack_bytes(self, pictures: dict[str, ASFByteArrayAttribute]):
        kind, attr = choice(list(pictures.items()))
        id3_type, size = WMA.EmbeddedImage._unpack_bytes(attr)
        assert id3_type == kind
        assert size < len(attr.value)

        with mock.patch.object(WMA.EmbeddedImage, "_get_type_from_number", side_effect=ValueError):
            id3_type, _ = WMA.EmbeddedImage._unpack_bytes(next(iter(pictures.values())))
            assert id3_type is None

    def test_get_bytes(self, pictures: dict[str, ASFByteArrayAttribute]):
        kind, attr = choice(list(pictures.items()))
        result = WMA.EmbeddedImage._get_bytes(choice([attr, attr.value]))
        assert isinstance(result, bytes)
        assert len(result) < len(attr.value)  # check that the header has been removed

        assert_validator_skips(WMA.EmbeddedImage._get_bytes, b"invalid data")


class TestWMA(LocalTrackTester):
    @pytest.fixture
    def model(self, uri: URI, faker: Faker, tmp_path: Path) -> MusifyModel:
        extension = choice(get_args(WMA.model_fields["format"].annotation))
        path = Path(tmp_path, faker.file_name(extension=extension)).absolute()
        return WMA(name=faker.sentence(), uri=uri, path=path)

    def test_deserialize_unicode_attribute(self, faker: Faker):
        expected = faker.sentence()
        attribute = ASFUnicodeAttribute(expected)
        assert WMA._deserialize_unicode_attribute(attribute) == expected

    def test_deserialize_unicode_attributes(self, faker: Faker):
        expected = [faker.sentence() for _ in range(faker.random_int(3, 6))]
        attributes = [ASFUnicodeAttribute(item) for item in expected]
        assert WMA._deserialize_unicode_attributes(attributes) == expected

    def test_from_tags(self, model: WMA, images: list[bytes], pictures: dict[str, ASFByteArrayAttribute], faker: Faker):
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
        assert model.images == {kind: WMA.EmbeddedImage.model_validate(attr) for kind, attr in pictures.items()}
