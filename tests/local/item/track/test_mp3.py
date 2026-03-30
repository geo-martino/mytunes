from argparse import Namespace
from copy import deepcopy
from datetime import date
from io import BytesIO
from pathlib import Path
from random import choice

import mutagen.id3
import pytest
from PIL import Image
from PIL.ImageFile import ImageFile as PILImageFile
from faker import Faker

from musify.local.item.artist import LocalArtist
from musify.local.item.track import TagContext
from musify.local.item.track.mp3 import MP3
from musify.models.properties.uri import URI
from tests.local.item.track.testers import LocalTrackEmbeddedImageTester, LocalTrackTester


@pytest.fixture
def pictures(
        image_bytes: list[bytes], image_types: set[str], image_objects: list[PILImageFile]
) -> dict[str, mutagen.id3.APIC]:
    pictures = {}

    for img_bytes, img_obj in zip(image_bytes, image_objects):
        picture_type = image_types.pop()
        pictures[picture_type] = mutagen.id3.APIC(
            encoding=mutagen.id3.Encoding.UTF8,
            mime=Image.MIME[img_obj.format],
            type=getattr(mutagen.id3.PictureType, picture_type),
            data=img_bytes
        )

    return pictures


class TestMP3EmbeddedImage(LocalTrackEmbeddedImageTester):
    @pytest.fixture
    def model(self, image_object: PILImageFile, image_type: str, faker: Faker) -> MP3.EmbeddedImage:
        return MP3.EmbeddedImage(
            path=faker.file_path(category="image"),
            type=image_type,
            mime=image_object.get_format_mimetype(),
            height=image_object.height,
            width=image_object.width,
        )

    def test_get_bytes(self, pictures: dict[str, mutagen.id3.APIC]):
        kind, attr = choice(list(pictures.items()))
        result = MP3.EmbeddedImage._get_bytes(choice((attr, attr.data)))
        assert result is attr.data


class TestMP3(LocalTrackTester):
    @pytest.fixture
    def model(self, uri: URI, faker: Faker, tmp_path: Path) -> MP3:
        extension = choice(tuple(MP3.supported_extensions))
        path = Path(tmp_path, faker.file_name(extension=extension)).absolute()
        return MP3(name=faker.sentence(), uri=uri, path=path)
    
    def test_merge_suffixed_tags(self, uri: URI, faker: Faker):
        data: dict[str, str | bytes | list] = {
            "TIT2": "Track title",
            "TPE1": "Artist name",
            "TALB": "Album name",
            "APIC:Cover Front": faker.image(),
            "APIC:Cover Back": faker.image(),
            "COMM": faker.sentence(),
            "COMM:URI:eng": str(uri),
            "COMM:ID3V1 COMMENT:eng": faker.sentence(),
        }

        expected = deepcopy(data)
        expected["APIC"] = [expected.pop(key) for key in list(expected) if key.startswith("APIC")]
        expected["COMM"] = [expected.pop(key) for key in list(expected) if key.startswith("COMM")]

        # noinspection PyCallingNonCallable
        assert MP3._merge_suffixed_tags(data, lambda x: x) == expected

    def test_format_to_tags(self, model: MP3, uri: URI, pictures: dict[str, mutagen.id3.APIC], faker: Faker):
        tags = {
            "TIT2": mutagen.id3.TIT2(text="Sleepwalk My Life Away"),
            "TPE1": mutagen.id3.TPE1(text="Metallica"),
            "TALB": mutagen.id3.TALB(text="72 Seasons"),
            "COMM": [
                mutagen.id3.COMM(text=faker.sentence(), desc="Description"),
                mutagen.id3.COMM(text=str(uri), desc="URI", lang="eng"),
            ],
            "APIC": list(pictures.values()),
        }
        info = Namespace(by_alias=True, context=None, mode="python")

        expected = {
            "TIT2": mutagen.id3.TIT2(text="Sleepwalk My Life Away"),
            "TPE1": mutagen.id3.TPE1(text="Metallica"),
            "TALB": mutagen.id3.TALB(text="72 Seasons"),
            "COMM:Description:XXX": tags["COMM"][0],
            "COMM:URI:eng": tags["COMM"][1],
        } | {f"APIC:{kind}": pic for kind, pic in pictures.items()}

        # noinspection PyTypeChecker
        assert model.__class__._format_to_tags(tags, handler=lambda x: x, info=info) == expected

    def test_deserialize_text_frame(self, faker: Faker):
        expected = faker.pystr()
        data = mutagen.id3.TextFrame(text=expected)
        assert MP3._deserialize_text_frame(data) == expected

    def test_deserialize_text_frames(self, faker: Faker):
        expected = [faker.pystr() for _ in range(faker.random_int(3, 6))]
        data = [mutagen.id3.TextFrame(text=item) for item in expected]
        assert MP3._deserialize_text_frame(data) == expected

    def test_deserialize_rating_frame(self, faker: Faker):
        rating = mutagen.id3.POPM(email=faker.email(), rating=faker.random_int(1, 5), count=1)
        assert MP3._deserialize_rating_frame(rating) == rating.rating

    def test_serialize_text_frame_from_string(self, model: MP3, faker: Faker):
        value = faker.sentence()
        info = Namespace(field_name="name", by_alias=True, context=None, mode="python")

        # noinspection PyTypeChecker
        result = model._serialize_text_frame(value, info=info)
        assert isinstance(result, mutagen.id3.TIT2)
        assert str(result) == value

    def test_serialize_text_frame_from_strings(self, model: MP3, faker: Faker):
        value = faker.words()
        expected = model._join_tags(value)
        info = Namespace(field_name="comments", by_alias=True, context=None, mode="python")

        # noinspection PyTypeChecker
        result = model._serialize_text_frame(value, info=info)
        assert isinstance(result, mutagen.id3.COMM)
        assert str(result) == expected

    def test_serialize_text_frame_from_names(self, model: MP3, artists: list[LocalArtist]):
        expected = model._join_tags(artist.name for artist in artists)
        info = Namespace(field_name="artists", by_alias=True, context=None, mode="python")

        # noinspection PyTypeChecker
        result = model._serialize_text_frame(artists, info=info)
        assert isinstance(result, mutagen.id3.TPE1)
        assert str(result) == expected

    def test_serialize_text_frames(self, model: MP3, faker: Faker):
        expected = [faker.sentence() for _ in range(faker.random_int(3, 6))]
        info = Namespace(field_name="comments", by_alias=True, context=None, mode="python")

        # noinspection PyTypeChecker
        result = model._serialize_text_frames(expected, info=info)
        assert all(isinstance(r, mutagen.id3.COMM) for r in result)
        assert list(map(str, result)) == expected

    def test_serialize_text_frames_includes_uris(self, model: MP3, faker: Faker):
        value = [faker.sentence() for _ in range(faker.random_int(3, 6))]
        expected = value + list(map(str, model.uris))
        info = Namespace(
            field_name="comments", by_alias=True, context=TagContext(map_uri_to_tag="comments"), mode="python"
        )

        # noinspection PyTypeChecker
        result = model._serialize_text_frames(value, info=info)
        assert all(isinstance(r, mutagen.id3.COMM) for r in result)
        assert list(map(str, result)) == expected

    def test_from_tags(
            self, model: MP3, uri: URI, image_bytes: list[bytes], pictures: dict[str, mutagen.id3.APIC], faker: Faker
    ):
        sep = choice(MP3._tag_sep)
        tags = {
            "TIT2": mutagen.id3.TIT2(text="Sleepwalk My Life Away"),
            "TPE1": mutagen.id3.TPE1(text="Metallica"),
            "TALB": mutagen.id3.TALB(text="72 Seasons"),
            "TPE2": mutagen.id3.TPE2(text="Metallica and friends"),
            "TCON": mutagen.id3.TCON(text=sep.join(("Hard Rock", "Metal", "Rock", "Thrash Metal"))),
            "TRCK": mutagen.id3.TRCK(text="04"),
            "TPOS": mutagen.id3.TPOS(text="1/2"),
            "TBPM": mutagen.id3.TBPM(text="124.931"),
            "TKEY": mutagen.id3.TKEY(text="B"),
            "TCMP": mutagen.id3.TCMP(text="1"),
            choice(("TDRC", "TDAT", "TDOR", "TYER", "TORY")): mutagen.id3.TDRC(text="2023-04-14"),
            choice(("COMM", "COMMENT")) + ":ID3V1 COMMENT:eng": mutagen.id3.COMM(text=faker.sentence()),
            choice(("COMM", "COMMENT")) + ":URI:eng": mutagen.id3.COMM(text=str(uri)),
        } | {f"APIC:{kind}": pic for kind, pic in pictures.items()}

        expected_images = {kind: MP3.EmbeddedImage.model_validate(attr) for kind, attr in pictures.items()}
        for image in expected_images.values():
            image.path = model.path

        context = TagContext(remote_source=uri.source, map_uri_to_tag="comments")
        model = MP3.model_validate(dict(**tags, path=model.path), context=context)

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
        assert sorted(model.comments) == sorted(str(val) for key, val in tags.items() if key.startswith("COMM"))
        assert model.images == expected_images

        assert model.source == uri.source
        assert model.uris == {uri}
        assert model.uri == uri

    def test_to_tags(self, model: MP3, uri: URI, pictures: dict[str, mutagen.id3.APIC], faker: Faker):
        model.name = "Sleepwalk My Life Away"
        model.artist = "Metallica"
        model.album = "72 Seasons"
        model.album_artist = "Metallica and friends"
        model.genres = ["Hard Rock", "Metal", "Rock", "Thrash Metal"]
        model.track = 4
        model.disc = (1, 2)
        model.bpm = 124.931
        model.key = "B"
        model.released_at = "2023-04-14"
        model.compilation = True
        model.comments = [faker.sentence()]
        model.uri = uri
        model.images = pictures

        expected = {
            "TIT2": mutagen.id3.TIT2(text="Sleepwalk My Life Away"),
            "TPE1": mutagen.id3.TPE1(text="Metallica"),
            "TALB": mutagen.id3.TALB(text="72 Seasons"),
            "TPE2": mutagen.id3.TPE2(text="Metallica and friends"),
            "TCON": mutagen.id3.TCON(text=model._join_tags(("Hard Rock", "Metal", "Rock", "Thrash Metal"))),
            "TRCK": mutagen.id3.TRCK(text="4"),
            "TPOS": mutagen.id3.TPOS(text="1/2"),
            "TBPM": mutagen.id3.TBPM(text="124.931"),
            "TKEY": mutagen.id3.TKEY(text="B"),
            "TDAT": mutagen.id3.TDAT(text="2023-04-14"),
            "TCMP": mutagen.id3.TCMP(text="1"),
            "COMM:1:eng": mutagen.id3.COMM(text=model.comments[0], lang="eng"),
            f"COMM:{uri.source}URI:eng": mutagen.id3.COMM(text=str(uri), lang="eng", desc=f"{uri.source}URI"),
        }

        loaded_images = {kind: Image.open(BytesIO(pic.data)) for kind, pic in pictures.items()}
        context = TagContext(map_uri_to_tag="comments", loaded_images=loaded_images)
        result = model.to_tags(context=context)

        assert {k: v for k, v in result.items() if not k.startswith("APIC")} == expected
        assert {k for k, v in result.items() if k.startswith("APIC")} == {f"APIC:{kind}" for kind in pictures}
