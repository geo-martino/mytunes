from argparse import Namespace
from copy import deepcopy
from datetime import date
from io import BytesIO
from pathlib import Path
from random import choice

import mutagen.flac
import mutagen.id3
import pytest
from PIL import Image
from PIL.ImageFile import ImageFile as PILImageFile
from faker import Faker

from mytunes._models.properties.date import SparseDate
from mytunes._models.properties.music import KeySignature
from mytunes._models.properties.order import Position
from mytunes._models.properties.uri import URI
from mytunes.local._item.genre import LocalGenre
from mytunes.local._item.track import TagContext
from mytunes.local._item.track.flac import FLAC
from tests.local.item.track.testers import LocalTrackTester, LocalTrackEmbeddedImageTester


@pytest.fixture
def pictures(
        image_bytes: list[bytes], image_objects: list[PILImageFile], image_types: set[str]
) -> dict[str, mutagen.flac.Picture]:
    pictures = {}

    for img_bytes, img_obj in zip(image_bytes, image_objects):
        image_type = image_types.pop()

        picture = mutagen.flac.Picture()
        picture.type = getattr(mutagen.id3.PictureType, image_type)
        picture.mime = Image.MIME[img_obj.format]
        picture.data = img_bytes
        pictures[image_type] = picture

    return pictures


@pytest.fixture
def file(pictures: dict[str, mutagen.flac.Picture], faker: Faker, tmp_path: Path) -> mutagen.flac.FLAC:
    path = tmp_path.joinpath(faker.file_name(category="audio"))

    file = mutagen.flac.FLAC()
    file.filename = str(path)
    file.tags = {"name": "Track title"}
    file.metadata_blocks = [p for p in pictures.values()]

    stream_info = mutagen.flac.StreamInfo.__new__(mutagen.flac.StreamInfo)
    stream_info.length = faker.random_int() / 100
    stream_info.channels = 2
    stream_info.bitrate = 320000
    stream_info.sample_rate = 44100
    stream_info.bits_per_sample = 16
    file.metadata_blocks.append(stream_info)

    return file


class TestFLACEmbeddedImage(LocalTrackEmbeddedImageTester):
    @pytest.fixture
    def model(self, image_object: PILImageFile, image_type: str, faker: Faker) -> FLAC.EmbeddedImage:
        return FLAC.EmbeddedImage(
            path=faker.file_path(category="image"),
            type=image_type,
            mime=image_object.get_format_mimetype(),
            height=image_object.height,
            width=image_object.width,
        )

    def test_get_bytes(self, pictures: dict[str, mutagen.flac.Picture]):
        kind, attr = choice(list(pictures.items()))
        result = FLAC.EmbeddedImage._get_bytes(choice((attr, attr.data)))
        assert result is attr.data

    async def test_get_tag_value(self, model: FLAC.EmbeddedImage, file: mutagen.flac.FLAC):
        file.filename = str(model.path)
        assert (await model._get_tag_value(file)).type == model.id3_type


class TestFLAC(LocalTrackTester):
    @pytest.fixture
    def model(self, uri: URI, faker: Faker, tmp_path: Path) -> FLAC:
        extension = choice(tuple(FLAC.supported_extensions))
        path = Path(tmp_path, faker.file_name(extension=extension)).absolute()
        return FLAC(name=faker.sentence(), uri=uri, path=path)

    # noinspection PyMethodOverriding
    @pytest.fixture
    def file(self, file: mutagen.flac.FLAC) -> mutagen.flac.FLAC:
        return file

    def test_extract_tags_from_mutagen(self, file: mutagen.flac.FLAC, faker: Faker):
        tags = faker.pydict()
        tags.pop("source", None)  # just in case the faker generates this key

        file.tags = deepcopy(tags)
        file.tags["source"] = [faker.word()]  # should be dropped

        assert file.filename
        assert file.pictures

        result = FLAC._extract_tags_from_mutagen(file)
        assert result == tags | dict(path=file.filename, audio=file, length=file.info.length, images=file.pictures)

    # noinspection PyCallingNonCallable
    def test_merge_position_values_skips(self):
        tags = {
            "title": ["Sleepwalk My Life Away"],
            "artist": ["Metallica"],
            "album": ["72 Seasons"],
            "albumartist": ["Metallica"],
        }
        result = FLAC._merge_position_values(tags)

        assert "track" not in result
        assert "disc" not in result

    # noinspection PyCallingNonCallable
    def test_merge_position_values(self):
        tags = {
            "title": ["Sleepwalk My Life Away"],
            "artist": ["Metallica"],
            "album": ["72 Seasons"],
            "albumartist": ["Metallica"],
            "track": 3,
            "tracknumber": 5,
            "tracktotal": 10,
            "discnumber": 2,
            "disctotal": 5,
        }
        result = FLAC._merge_position_values(tags)

        assert result["track"] == ("3", "10")
        assert result["disc"] == ("2", "5")

    # noinspection PyCallingNonCallable
    def test_merge_position_values_splits_appropriately(self):
        tags = {
            "title": ["Sleepwalk My Life Away"],
            "artist": ["Metallica"],
            "album": ["72 Seasons"],
            "albumartist": ["Metallica"],
            "track": ["3/5"],
            "tracktotal": ["10/20"],
            "discnumber": 2,
            "disctotal": ["5/15"],
            "path": "/music/Metallica/72 Seasons/04 Sleepwalk My Life Away.flac",
        }
        result = FLAC._merge_position_values(tags)

        assert result["track"] == ("3", "20")
        assert result["disc"] == ("2", "15")

    def test_format_to_tags(self, model: FLAC, uri: URI, faker: Faker):
        tags = {
            "title": ["Sleepwalk My Life Away"],
            "artist": ["Metallica"],
            "track": {
                "tracknumber": "04",
                "tracktotal": "08",
            },
            "discnumber": {
                "discnumber": "1",
                "disctotal": "2",
            },
            "bpm": "124.931",
            "date": "2023-04-14",
            "comment": [*faker.words(), str(uri)],
        }
        expected = {
            "title": tags["title"],
            "artist": tags["artist"],
            "tracknumber": ["04"],
            "tracktotal": ["08"],
            "discnumber": ["1"],
            "disctotal": ["2"],
            "bpm": [tags["bpm"],],
            "date": [tags["date"]],
            "comment": tags["comment"],
        }
        info = Namespace(by_alias=True, mode="python")

        # noinspection PyTypeChecker
        assert model._format_to_tags(lambda x: tags, info=info) == expected

    def test_serialize_string(self, model: FLAC, faker: Faker):
        value = choice((
            SparseDate(year=2021, month=12, day=31),
            KeySignature(root=2, mode=1)
        ))
        info = Namespace(field_name="comments", by_alias=True, context=None, mode="python")
        # noinspection PyTypeChecker
        assert model._serialize_string(value, handler=lambda x: x, info=info) == str(value)

    def test_serialize_strings(self, model: FLAC, genres: list[LocalGenre], faker: Faker):
        value = genres + [faker.sentence() for _ in range(faker.random_int(3, 6))]
        expected = [genre.name for genre in genres] + value[len(genres):]
        info = Namespace(field_name="comments", by_alias=True, context=None, mode="python")
        # noinspection PyTypeChecker
        assert model._serialize_strings(value, handler=lambda x: x, info=info) == expected

    def test_serialize_strings_includes_uris(self, model: FLAC, faker: Faker):
        value = [faker.sentence() for _ in range(faker.random_int(3, 6))]
        expected = value + list(map(str, model.uris))
        context = TagContext(map_uri_to_field="comments")
        info = Namespace(field_name="comments", by_alias=True, context=context, mode="python")
        # noinspection PyTypeChecker
        assert model._serialize_strings(value, handler=lambda x: x, info=info) == expected

    def test_serialize_position_tags_skips(self, model: FLAC):
        info = Namespace(by_alias=True, mode="python")
        value = ()
        # noinspection PyTypeChecker
        assert model._serialize_position_tags(value, handler=lambda x: x, info=info) is value

    def test_serialize_position_tags(self, model: FLAC):
        info = Namespace(field_name="disc", by_alias=True, context=None, mode="python")

        position = Position(number=1, total=2, zero_fill=3)
        expected = {"discnumber": "001", "disctotal": "002"}
        # noinspection PyTypeChecker
        assert model._serialize_position_tags(position, handler=lambda x: x, info=info) == expected

        position = Position(number=1, zero_fill=2)
        expected = {"discnumber": "01"}
        # noinspection PyTypeChecker
        assert model._serialize_position_tags(position, handler=lambda x: x, info=info) == expected

        position = Position(total=3, zero_fill=2)
        expected = {"disctotal": "03"}
        # noinspection PyTypeChecker
        assert model._serialize_position_tags(position, handler=lambda x: x, info=info) == expected

    def test_from_tags(
            self,
            model: FLAC,
            uri: URI,
            image_bytes: list[bytes],
            pictures: dict[str, mutagen.flac.Picture],
            faker: Faker,
    ):
        sep = choice(FLAC._tag_sep)
        tags = {
            "title": ["Sleepwalk My Life Away"],
            "artist": ["Metallica"],
            "album": ["72 Seasons"],
            "albumartist": ["Metallica and friends"],
            "genre": ["Hard Rock", "Metal" + sep + "Rock", "Thrash Metal"],
            choice(("tracknumber", "tracktotal")): ["04"],
            "discnumber": ["1"],
            "disctotal": ["2"],
            "bpm": ["124.931"],
            "key": ["B"],
            choice(("date", "year")): ["2023-04-14"],
            choice(("comment", "description")): [str(uri)],
            "compilation": ["1"],
            "images": list(pictures.values()),
        }

        expected_images = {kind: FLAC.EmbeddedImage.model_validate(attr) for kind, attr in pictures.items()}
        for image in expected_images.values():
            image.path = model.path

        context = TagContext(remote_source=uri.source, map_uri_to_field="comments")
        model = FLAC.model_validate(dict(**tags, path=model.path), context=context)

        assert model.name == "Sleepwalk My Life Away"
        assert model.artist == "Metallica"
        assert model.album.name == "72 Seasons"
        assert model.album_artist.name == "Metallica and friends"
        assert [genre.name for genre in model.genres] == ["Hard Rock", "Metal", "Rock", "Thrash Metal"]
        assert model.track.number == 4
        assert model.track.total is None
        assert model.disc.number == 1
        assert model.disc.total == 2
        assert model.bpm == 124.931
        assert model.key.key == "B"
        assert model.released_at == date(2023, 4, 14)
        assert model.compilation is True
        assert model.comments == [str(uri)]
        assert model.images == expected_images

        assert model.source == uri.source
        assert model.uris == {uri}
        assert model.uri == uri

    def test_to_tags(self, model: FLAC, uri: URI, pictures: dict[str, mutagen.flac.Picture], faker: Faker):
        model.name = "Sleepwalk My Life Away"
        model.artist = "Metallica"
        model.album = "72 Seasons"
        model.album_artist = "Metallica and friends"
        model.genres = ["Hard Rock", "Metal", "Rock", "Thrash Metal"]
        model.track = 4
        model.track.zero_fill = 2
        model.disc = (1, 2)
        model.bpm = 124.931
        model.key = "B"
        model.released_at = "2023-04-14"
        model.compilation = True
        model.comments = [faker.sentence()]
        model.uri = uri
        model.images = pictures

        expected = {
            "title": ["Sleepwalk My Life Away"],
            "artist": ["Metallica"],
            "album": ["72 Seasons"],
            "albumartist": ["Metallica and friends"],
            "genre": ["Hard Rock", "Metal", "Rock", "Thrash Metal"],
            "tracknumber": ["04"],
            "discnumber": ["1"],
            "disctotal": ["2"],
            "bpm": ["124.931"],
            "initialkey": ["B"],
            "date": ["2023-04-14"],
            "compilation": ["1"],
            "comment": [*model.comments, str(uri)],
        }

        loaded_images = {kind: Image.open(BytesIO(pic.data)) for kind, pic in pictures.items()}
        context = TagContext(map_uri_to_field="comments", loaded_images=loaded_images)
        result = model.to_tags(context=context)

        assert {k: v for k, v in result.items() if k != "images"} == expected
        result_image_types = {pic.type for k, v in result.items() if k == "images" for pic in v}
        assert result_image_types == {pic.type for pic in pictures.values()}
