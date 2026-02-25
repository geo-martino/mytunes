import struct
from argparse import Namespace
from datetime import date
from io import BytesIO
from pathlib import Path
from random import choice
from unittest.mock import patch

import mutagen.id3
import pytest
from PIL import Image
from PIL.ImageFile import ImageFile as PILImageFile
from faker import Faker
# noinspection PyProtectedMember
from mutagen.asf import ASFUnicodeAttribute, ASFByteArrayAttribute

from musify.local.item.genre import LocalGenre
from musify.local.item.track import TagDumpContext
from musify.local.item.track.wma import WMA
from musify.models.properties.order import Position
from musify.models.properties.uri import URI
from tests.local.item.track.testers import LocalTrackEmbeddedImageTester, LocalTrackTester
from tests.utils import assert_validator_skips


@pytest.fixture
def pictures(
        image_bytes: list[bytes], image_objects: list[PILImageFile], image_types: set[str]
) -> dict[str, ASFByteArrayAttribute]:
    pictures = {}
    for img_bytes, img_obj in zip(image_bytes, image_objects):
        kind = image_types.pop()

        header = struct.pack("<bi", int(getattr(mutagen.id3.PictureType, kind)), len(img_bytes))
        mime = Image.MIME[img_obj.format].encode("utf-16")
        description = "".encode("utf-16")
        data = b"\x00\x00".join((header + mime, description, img_bytes))

        pictures[kind] = ASFByteArrayAttribute(data)

    return pictures


class TestWMAEmbeddedImage(LocalTrackEmbeddedImageTester):
    @pytest.fixture
    def model(self, image_object: PILImageFile, image_type: str, faker: Faker) -> WMA.EmbeddedImage:
        return WMA.EmbeddedImage(
            path=faker.file_path(category="image"),
            type=image_type,
            mime=image_object.get_format_mimetype(),
            height=image_object.height,
            width=image_object.width,
        )

    def test_unpack_bytes(self, pictures: dict[str, ASFByteArrayAttribute]):
        kind, attr = choice(list(pictures.items()))
        id3_type, size = WMA.EmbeddedImage._unpack_bytes(attr)
        assert id3_type == kind
        assert size < len(attr.value)

        with patch.object(WMA.EmbeddedImage, "_get_type_from_number", side_effect=ValueError):
            id3_type, _ = WMA.EmbeddedImage._unpack_bytes(next(iter(pictures.values())))
            assert id3_type is None

    def test_get_bytes(self, pictures: dict[str, ASFByteArrayAttribute]):
        kind, attr = choice(list(pictures.items()))
        result = WMA.EmbeddedImage._get_bytes(choice((attr, attr.value)))
        assert isinstance(result, bytes)
        assert len(result) < len(attr.value)  # check that the header has been removed

        assert_validator_skips(WMA.EmbeddedImage._get_bytes, b"invalid data")


class TestWMA(LocalTrackTester):
    @pytest.fixture
    def model(self, uri: URI, faker: Faker, tmp_path: Path) -> WMA:
        extension = choice(tuple(WMA.__supported_extensions__))
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

    def test_serialize_unicode_attribute_skips_on_json(self, model: WMA, faker: Faker):
        value = choice(([faker.sentence()], faker.words()))
        info = Namespace(field_name="comments", by_alias=True, context=None, mode="json")
        # noinspection PyTypeChecker
        assert not isinstance(model._serialize_unicode_attribute(value, info=info), ASFUnicodeAttribute)

    def test_serialize_unicode_attribute(self, model: WMA, faker: Faker):
        value = choice(([faker.sentence()], faker.words()))
        expected = model._join_tags(value)
        info = Namespace(field_name="comments", by_alias=True, context=None, mode="python")
        # noinspection PyTypeChecker
        assert model._serialize_unicode_attribute(value, info=info) == expected

    def test_serialize_unicode_attributes(self, model: WMA, genres: list[LocalGenre], faker: Faker):
        value = genres + [faker.sentence() for _ in range(faker.random_int(3, 6))]
        expected = [genre.name for genre in genres] + value[len(genres):]
        info = Namespace(field_name="comments", by_alias=True, context=None, mode="python")
        # noinspection PyTypeChecker
        assert model._serialize_unicode_attributes(value, info=info) == expected

    def test_serialize_unicode_attributes_includes_uris(self, model: WMA, faker: Faker):
        value = [faker.sentence() for _ in range(faker.random_int(3, 6))]
        expected = value + list(map(str, model.uris))
        info = Namespace(
            field_name="comments", by_alias=True, context=TagDumpContext(map_uri_to_tag="comments"), mode="python"
        )
        # noinspection PyTypeChecker
        assert model._serialize_unicode_attributes(value, info=info) == expected

    def test_serialize_position_tags_skips(self, model: WMA):
        info = Namespace(by_alias=True, mode="python")
        # noinspection PyTypeChecker
        assert model._serialize_position_tags((), info) is None

    def test_serialize_position_tags(self, model: WMA):
        info = Namespace(field_name="track", by_alias=True, context=None, mode="python")

        position = Position(number=1, total=2, zero_fill=3)
        expected = {"WM/TrackNumber": "001", "TotalTracks": "002"}
        # noinspection PyTypeChecker
        assert model._serialize_position_tags(position, info=info) == expected

        position = Position(number=1, zero_fill=2)
        expected = {"WM/TrackNumber": "01"}
        # noinspection PyTypeChecker
        assert model._serialize_position_tags(position, info=info) == expected

        position = Position(total=3, zero_fill=2)
        expected = {"TotalTracks": "03"}
        # noinspection PyTypeChecker
        assert model._serialize_position_tags(position, info=info) == expected

    def test_format_to_tags(self, model: WMA, uri: URI, faker: Faker):
        tags = {
            "Title": [ASFUnicodeAttribute("Sleepwalk My Life Away")],
            "Author": [ASFUnicodeAttribute("Metallica")],
            "WM/TrackNumber": {
                "WM/TrackNumber": ASFUnicodeAttribute("04"),
                "TotalTracks": ASFUnicodeAttribute("08"),
            },
            "WM/PartOfSet": ASFUnicodeAttribute("1/2"),
            "WM/InitialKey": ASFUnicodeAttribute("B"),
            "WM/Comments": list(map(ASFUnicodeAttribute, [*model.comments, str(uri)])),
        }
        expected = {
            "Title": tags["Title"],
            "Author": tags["Author"],
            "WM/TrackNumber": [ASFUnicodeAttribute("04")],
            "TotalTracks": [ASFUnicodeAttribute("08")],
            "WM/PartOfSet": [tags["WM/PartOfSet"]],
            "WM/InitialKey": [tags["WM/InitialKey"]],
            "WM/Comments": tags["WM/Comments"],
        }
        info = Namespace(by_alias=True, mode="python")

        # noinspection PyTypeChecker
        assert model._format_to_tags(lambda x: tags, info=info) == expected

    def test_from_tags(
            self, model: WMA, image_bytes: list[bytes], pictures: dict[str, ASFByteArrayAttribute], faker: Faker
    ):
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

    def test_to_tags(self, model: WMA, uri: URI, pictures: dict[str, mutagen.asf.ASFByteArrayAttribute], faker: Faker):
        model.name = "Sleepwalk My Life Away"
        model.artist = "Metallica"
        model.album = "72 Seasons"
        model.genres = ["Hard Rock", "Metal", "Rock", "Thrash Metal"]
        model.track = 4
        model.track.zero_fill = 2
        model.disc = (1, 2)
        model.bpm = 124.931
        model.key = "B"
        model.released_at = "2023-04-14"
        model.comments = [faker.sentence()]
        model.uri = uri
        model.images = pictures

        expected = {
            "Title": [ASFUnicodeAttribute("Sleepwalk My Life Away")],
            "Author": [ASFUnicodeAttribute("Metallica")],
            "WM/AlbumTitle": [ASFUnicodeAttribute("72 Seasons")],
            "WM/Genre": [
                ASFUnicodeAttribute("Hard Rock"),
                ASFUnicodeAttribute("Metal"),
                ASFUnicodeAttribute("Rock"),
                ASFUnicodeAttribute("Thrash Metal")
            ],
            "WM/TrackNumber": [ASFUnicodeAttribute("04")],
            "WM/PartOfSet": [ASFUnicodeAttribute("1/2")],
            "WM/BeatsPerMinute": [ASFUnicodeAttribute("124.931")],
            "WM/InitialKey": [ASFUnicodeAttribute("B")],
            "WM/Year": [ASFUnicodeAttribute("2023-04-14")],
            "WM/Comments": list(map(ASFUnicodeAttribute, [*model.comments, str(uri)])),
        }

        loaded_images = {
            kind: Image.open(BytesIO(WMA.EmbeddedImage._get_bytes(pic)))
            for kind, pic in pictures.items()
        }
        context = TagDumpContext(map_uri_to_tag="comments", loaded_images=loaded_images)
        result = model.to_tags(context=context)

        assert {k: v for k, v in result.items() if k != "WM/Picture"} == expected
        result_image_types = {
            WMA.EmbeddedImage.get_id3_type_from_tag(pic) for k, v in result.items()
            if k == "WM/Picture" for pic in v
        }
        assert result_image_types == {
            WMA.EmbeddedImage.get_id3_type_from_tag(pic) for pic in pictures.values()
        }
