from argparse import Namespace
from datetime import date
from io import BytesIO
from pathlib import Path
from random import choice

import mutagen.id3
import pytest
from PIL import Image
from PIL.ImageFile import ImageFile as PILImageFile
from faker import Faker
from mutagen.mp4 import MP4FreeForm, MP4Cover
from mytunes._models.properties.date import SparseDate
from mytunes._models.properties.music import KeySignature
from mytunes._models.properties.order import Position
from mytunes._models.properties.uri import URI
from mytunes.local._item.genre import LocalGenre
from mytunes.local._item.track import TagContext
from mytunes.local._item.track.m4a import M4A
from tests.local.item.track.testers import LocalTrackTester, LocalTrackEmbeddedImageTester


@pytest.fixture
def pictures(image_bytes: list[bytes], image_types: set[str]) -> dict[str, mutagen.mp4.MP4Cover]:
    # AFAIK, MP4 only supports a single image per track so we just check for a single image type
    return {"COVER_FRONT": mutagen.mp4.MP4Cover(choice(image_bytes))}


class TestM4AEmbeddedImage(LocalTrackEmbeddedImageTester):
    @pytest.fixture
    def model(self, image_object: PILImageFile, image_type: str, faker: Faker) -> M4A.EmbeddedImage:
        return M4A.EmbeddedImage(
            path=faker.file_path(category="image"),
            type=image_type,
            mime=image_object.get_format_mimetype(),
            height=image_object.height,
            width=image_object.width,
        )

    def test_get_bytes(self, pictures: dict[str, mutagen.mp4.MP4Cover]):
        kind, attr = choice(list(pictures.items()))
        result = M4A.EmbeddedImage._get_bytes(choice((attr, bytes(attr))))
        assert result == bytes(attr)


class TestM4A(LocalTrackTester):
    @pytest.fixture
    def model(self, uri: URI, faker: Faker, tmp_path: Path) -> M4A:
        extension = choice(tuple(M4A.supported_extensions))
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

    def test_format_to_tags(self, model: M4A, uri: URI, faker: Faker):
        tags = {
            "©nam": ["Sleepwalk My Life Away"],
            "©ART": "Metallica",
            "©alb": "72 Seasons",
            "©gen": ["Hard Rock", "Metal", "Rock", "Thrash Metal"],
            "trkn": [(4,)],
            "disk": [(1, 2)],
            "tmpo": [124],
            "----:com.apple.iTunes:INITIALKEY": "B",
            "©day": ["2023-04-14"],
        }
        expected = {
            "©nam": ["Sleepwalk My Life Away"],
            "©ART": ["Metallica"],
            "©alb": ["72 Seasons"],
            "©gen": ["Hard Rock", "Metal", "Rock", "Thrash Metal"],
            "trkn": [(4,)],
            "disk": [(1, 2)],
            "tmpo": [124],
            "----:com.apple.iTunes:INITIALKEY": [MP4FreeForm(b"B")],
            "©day": ["2023-04-14"],
        }
        info = Namespace(by_alias=True, mode="python")

        # noinspection PyTypeChecker
        assert model._format_to_tags(lambda x: tags, info=info) == expected

    def test_serialize_string(self, model: M4A, faker: Faker):
        value = choice((
            SparseDate(year=2021, month=12, day=31),
            KeySignature(root=2, mode=1)
        ))
        info = Namespace(field_name="comments", by_alias=True, context=None, mode="python")
        # noinspection PyTypeChecker
        assert model._serialize_string(value, handler=lambda x: x, info=info) == str(value)

    def test_serialize_strings(self, model: M4A, genres: list[LocalGenre], faker: Faker):
        value = genres + [faker.sentence() for _ in range(faker.random_int(3, 6))]
        expected = [genre.name for genre in genres] + value[len(genres):]
        info = Namespace(field_name="comments", by_alias=True, context=None, mode="python")

        # noinspection PyTypeChecker
        assert model._serialize_strings(value, handler=lambda x: x, info=info) == expected

    def test_serialize_strings_includes_uris(self, model: M4A, faker: Faker):
        value = [faker.sentence() for _ in range(faker.random_int(3, 6))]
        expected = value + list(map(str, model.uris))
        context = TagContext(map_uri_to_field="comments")
        info = Namespace(field_name="comments", by_alias=True, context=context, mode="python")

        # noinspection PyTypeChecker
        assert model._serialize_strings(value, handler=lambda x: x, info=info) == expected

    def test_serialize_bpm_skips(self, model: M4A, faker: Faker):
        info = Namespace(by_alias=True, mode="python")
        # noinspection PyTypeChecker
        assert model._serialize_bpm(None, info=info) is None

    def test_serialize_bpm(self, model: M4A, faker: Faker):
        bpm = faker.random_int(6000, 15000) / 100
        info = Namespace(by_alias=True, mode="python")
        # noinspection PyTypeChecker
        assert model._serialize_bpm(bpm, info=info) == [int(bpm)]

    def test_serialize_position_tags_skips(self, model: M4A):
        info = Namespace(by_alias=True, mode="python")
        # noinspection PyTypeChecker
        assert model._serialize_position_tags((), handler=lambda x: x, info=info) is None

    def test_serialize_position_tags(self, model: M4A):
        position = Position(number=1, total=2, zero_fill=3)
        info = Namespace(by_alias=True, mode="python")
        # noinspection PyTypeChecker
        assert model._serialize_position_tags(position, handler=lambda x: x, info=info) == [position.numbers]

    def test_from_tags(
            self,
            model: M4A,
            uri: URI,
            image_bytes: list[bytes],
            pictures: dict[str, mutagen.mp4.MP4Cover],
            faker: Faker,
    ):
        sep = choice(M4A._tag_sep)
        tags = {
            "©nam": ["Sleepwalk My Life Away"],
            "©ART": ["Metallica"],
            "©alb": ["72 Seasons"],
            "aART": ["Metallica and friends"],
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
            "©cmt": [str(uri)],
            "covr": list(map(MP4Cover, image_bytes)),
            "cpil": True,
        }

        expected_images = {kind: M4A.EmbeddedImage.model_validate(attr) for kind, attr in pictures.items()}
        for image in expected_images.values():
            image.path = model.path

        context = TagContext(remote_source=uri.source, map_uri_to_field="comments")
        model = M4A.model_validate(dict(**tags, path=model.path), context=context)

        assert model.name == "Sleepwalk My Life Away"
        assert model.artist == "Metallica"
        assert model.album.name == "72 Seasons"
        assert model.album_artist.name == "Metallica and friends"
        assert [genre.name for genre in model.genres] == ["Hard Rock", "Metal", "Rock", "Thrash Metal"]
        assert model.track.number == 4
        assert model.track.total is None
        assert model.disc.number == 1
        assert model.disc.total == 2
        assert model.bpm == 124
        assert model.key.key == "B"
        assert model.released_at == date(2023, 4, 14)
        assert model.compilation is True
        assert model.comments == [str(uri)]
        assert model.images == expected_images

        assert model.source == uri.source
        assert model.uris == {uri}
        assert model.uri == uri

    def test_to_tags(self, model: M4A, uri: URI, pictures: dict[str, mutagen.mp4.MP4Cover], faker: Faker):
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
            "©nam": ["Sleepwalk My Life Away"],
            "©ART": ["Metallica"],
            "©alb": ["72 Seasons"],
            "aART": ["Metallica and friends"],
            "©gen": ["Hard Rock", "Metal", "Rock", "Thrash Metal"],
            "trkn": [(4,)],
            "disk": [(1, 2)],
            "tmpo": [124],
            "----:com.apple.iTunes:INITIALKEY": [MP4FreeForm(b"B")],
            "©day": ["2023-04-14"],
            "cpil": True,
            "©cmt": [*model.comments, str(uri)],
        }

        loaded_images = {kind: Image.open(BytesIO(bytes(pic))) for kind, pic in pictures.items()}
        context = TagContext(map_uri_to_field="comments", loaded_images=loaded_images)
        result = model.to_tags(context=context)

        assert {k: v for k, v in result.items() if k != "covr"} == expected
        assert sum(len(v) for k, v in result.items() if k.startswith("covr")) == len(pictures)
