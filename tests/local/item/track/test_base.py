from argparse import Namespace
from datetime import date
from pathlib import Path
from random import choice, sample
from typing import Any
from unittest.mock import patch

import mutagen
import mutagen.wave
import pytest
from faker import Faker
from pydantic import TypeAdapter

from musify.local.item.artist import LocalArtist
from musify.local.item.track import LocalTrack, TagDumpContext
from musify.models.properties.file import IsLocalFile
from musify.models.properties.image import ImageFile
from musify.models.properties.length import HasLength
from musify.models.properties.uri import HasMutableURI
from tests.models.testers import UniqueKeyTester
from tests.utils import assert_validator_skips, SimpleURI


class TestLocalTrack(UniqueKeyTester):
    @pytest.fixture
    def model(self, tags: dict[str, Any], faker: Faker) -> LocalTrack:
        uri = SimpleURI.from_id(
            faker.random_int(int(10e9), int(10e10)), kind=LocalTrack.type, source=faker.word()
        )
        return LocalTrack(**tags, uri=uri, path=faker.file_path())

    @pytest.fixture
    def tags(self, image_files: list[ImageFile]) -> dict[str, Any]:
        sep = choice(LocalTrack._tag_sep)
        return {
            "name": ["Sleepwalk My Life Away"],
            "artists": ["Metallica"],
            "album": ["72 Seasons"],
            "album artist": ["Metallica"],
            "genres": ["Hard Rock", "Metal" + sep + "Rock", "Thrash Metal"],
            "track": ["04"],
            "disc": ["1/2"],
            "bpm": ["124.931"],
            "key": ["B"],
            "released_at": ["2023-04-14"],
            "comments": ["spotify:track:1WjgFpSxwA0Bqyr7hWc3f1"],
            "compilation": ["0"],
            "images": image_files,
        }

    @pytest.fixture
    def file(self, tags: dict[str, Any], faker: Faker, tmp_path: Path) -> mutagen.FileType:
        path = tmp_path.joinpath(faker.file_name(category="audio"))

        file = mutagen.FileType()
        file.filename = str(path)
        file.tags = tags

        stream_info = mutagen.wave.WaveStreamInfo.__new__(mutagen.wave.WaveStreamInfo)
        stream_info.length = faker.random_int() / 100
        stream_info.channels = 2
        stream_info.bitrate = 320000
        stream_info.sample_rate = 44100
        stream_info.bits_per_sample = 16
        file.info = stream_info

        return file

    ###########################################################################
    ## Utility Methods
    ###########################################################################
    async def test_from_path(self, file: mutagen.FileType):
        with patch.object(LocalTrack, "load_file", return_value=file) as mock_load:
            model = await LocalTrack.from_path(file.filename)
            mock_load.assert_called_once_with(file.filename)
            assert model.name == file["name"][0]

    async def test_load_file(self, faker: Faker, tmp_path: Path):
        path = tmp_path.joinpath(faker.file_name(category="audio"))
        path.touch()  # needs a real file to open
        file = mutagen.FileType()

        with patch.object(mutagen, "File", return_value=file) as mock_file:
            result = await LocalTrack.load_file(path)

            mock_file.assert_called_once()
            assert result is file
            assert result.filename == str(path)

    @pytest.mark.skip(reason="Not implemented yet")
    def test_get_tag_id(self):
        pass  # TODO

    ###########################################################################
    ## Validators/Serializers
    ###########################################################################
    # noinspection PyCallingNonCallable
    def test_extract_tags_from_mutagen(self, file: mutagen.FileType, tags: dict[str, Any]):
        assert file.filename

        result = LocalTrack._extract_tags_from_mutagen(file)
        assert result == tags | dict(
            path=file.filename,
            length=file.info.length,
            channels=2,
            bit_rate=320.0,
            bit_depth=16,
            sample_rate=44.1,
        )

    def test_extract_first_value_from_sequence(self):
        # noinspection PyTypeChecker
        assert LocalTrack._extract_first_value_from_sequence(None) is None
        assert LocalTrack._extract_first_value_from_sequence("Track name") == "Track name"
        assert LocalTrack._extract_first_value_from_sequence(["Track name"]) == "Track name"

        value = ["Track name", "Artist name"]
        assert LocalTrack._extract_first_value_from_sequence(value) == "Track name"

    def test_extract_first_value_from_sequence_skips(self, faker: Faker):
        assert_validator_skips(LocalTrack._extract_first_value_from_sequence, None)
        assert_validator_skips(LocalTrack._extract_first_value_from_sequence, faker.pystr())
        assert_validator_skips(LocalTrack._extract_first_value_from_sequence, faker.pyint())

    def test_extract_first_value_from_single_sequence(self):
        # noinspection PyTypeChecker
        assert LocalTrack._extract_first_value_from_single_sequence(None) is None
        assert LocalTrack._extract_first_value_from_single_sequence("Track name") == "Track name"
        assert LocalTrack._extract_first_value_from_single_sequence(["Track name"]) == "Track name"

    def test_extract_first_value_from_single_sequence_skips(self, faker: Faker):
        assert_validator_skips(LocalTrack._extract_first_value_from_single_sequence, None)
        assert_validator_skips(LocalTrack._extract_first_value_from_single_sequence, faker.pystr())
        assert_validator_skips(LocalTrack._extract_first_value_from_single_sequence, faker.pyint())
        assert_validator_skips(LocalTrack._extract_first_value_from_single_sequence, faker.pytuple())
        assert_validator_skips(LocalTrack._extract_first_value_from_single_sequence, faker.pylist())
        assert_validator_skips(LocalTrack._extract_first_value_from_single_sequence, faker.pydict())

    def test_nullify(self):
        assert LocalTrack._nullify(None) is None
        assert LocalTrack._nullify([]) is None
        assert LocalTrack._nullify(["", ""]) is None

        expected = ["12", 20]
        assert LocalTrack._nullify(expected) == expected

    def test_nullify_skips(self, faker: Faker):
        assert_validator_skips(LocalTrack._extract_first_value_from_single_sequence, None)
        assert_validator_skips(LocalTrack._extract_first_value_from_single_sequence, faker.pystr())
        assert_validator_skips(LocalTrack._extract_first_value_from_single_sequence, faker.pyint())
        assert_validator_skips(LocalTrack._extract_first_value_from_single_sequence, faker.pytuple())
        assert_validator_skips(LocalTrack._extract_first_value_from_single_sequence, faker.pylist())
        assert_validator_skips(LocalTrack._extract_first_value_from_single_sequence, faker.pydict())

    def test_split_joined_tags(self, faker: Faker):
        tags = faker.words(nb=faker.random_int(10, 20))
        sep = choice(LocalTrack._tag_sep)
        tags_joined = [sep.join(tags[:3]), sep.join(tags[3:7]), sep.join(tags[7:])]
        assert LocalTrack._split_joined_tags(tags_joined) == tags

    def test_split_joined_tags_skips(self, faker: Faker):
        assert_validator_skips(LocalTrack._split_joined_tags, None)
        assert_validator_skips(LocalTrack._split_joined_tags, faker.pyint())

    def test_join_split_tags(self, model: LocalTrack, artists: list[LocalArtist], faker: Faker):
        model.artists = artists
        assert LocalTrack._join_split_tags(artists) == model.artist

    def test_map_images_skips(self, faker: Faker):
        assert_validator_skips(LocalTrack._map_images, None)
        assert_validator_skips(LocalTrack._map_images, faker.pystr())
        assert_validator_skips(LocalTrack._map_images, faker.pyint())

    def test_serialize_images_skips(self, model: LocalTrack, image_bytes: list[bytes]):
        # skips when not serializing by alias
        info = Namespace(by_alias=False, context=None, mode="python")
        # noinspection PyTypeChecker
        results = model._serialize_images(model.images, info=info)
        assert results is model.images

        # skips when loaded_images are not available
        info = Namespace(by_alias=True, context=TagDumpContext(), mode="python")
        # noinspection PyTypeChecker
        results = model._serialize_images(model.images, info=info)
        assert not results

    def test_from_tags(self, image_files: list[ImageFile], tags: dict[str, Any], faker: Faker):
        model = LocalTrack(**tags, path=faker.file_path())
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
        assert model.comments == tags["comments"]

        # only sets the first image of each image type
        expected = {}
        for img in image_files:
            if img.type not in expected:
                expected[img.type] = img
        assert model.images == expected

    ###########################################################################
    ## IO
    ###########################################################################
    async def test_load(
        self,
        model: LocalTrack,
        adapter: TypeAdapter[LocalTrack],
        file: mutagen.FileType,
        tags: dict[str, Any]
    ):
        expected = adapter.validate_python(tags | dict(path=file.filename))

        with patch.object(LocalTrack, "load_file", return_value=file) as mock_load:
            await model.load()

            mock_load.assert_called_once()
            assert model is not expected
            assert model.name == expected.name
            assert model.artist == expected.artist
            assert model.album.name == expected.album.name
            assert model.genre == expected.genre

    async def test_save(self, model: LocalTrack, file: mutagen.FileType, faker: Faker):
        with patch.object(file.__class__, "save") as mock_save:
            await model.save(file)
            mock_save.assert_called_once()

    def test_clear_all_tags(self, file: mutagen.FileType, faker: Faker):
        expected = set(file.tags.keys())
        result = LocalTrack.clear(file)
        assert set(result) == expected & LocalTrack.__tag_fields__

    def test_clear_selected_tags(self, file: mutagen.FileType, faker: Faker):
        include = sample(list(set(file.tags) & set(LocalTrack.__tag_fields__)), k=4)
        result = LocalTrack.clear(file, include=include)
        assert set(result) == set(include)

    def test_clear_selected_tags_with_exclude(self, file: mutagen.FileType, faker: Faker):
        include = sample(list(set(file.tags) & set(LocalTrack.__tag_fields__)), k=4)
        exclude = sample(list(set(file.tags) & set(LocalTrack.__tag_fields__)), k=4)
        result = LocalTrack.clear(file, include=include, exclude=exclude)
        assert set(result) == set(t for t in include if t not in exclude)

    def test_clear_tag(self, file: mutagen.FileType, tags: dict[str, Any]):
        tag_id = choice(list(tags))
        assert LocalTrack._clear_tag(file, tag_id=tag_id) == {tag_id}
        assert tag_id not in file.tags

        tag_id = "does not exist"
        assert tag_id not in file.tags
        assert not LocalTrack._clear_tag(file, tag_id=tag_id)
        assert tag_id not in file.tags

    # noinspection PyTestUnpassedFixture
    def test_to_selected_tags(self, model: LocalTrack):
        tags = model.to_tags(include={"name", "artists", "album", "does not exist"}, exclude={"name"})
        assert "title" not in tags
        assert "artists" in tags
        assert "album" in tags
        assert "genres" not in tags

        tags = model.to_tags(exclude={"name", "artists", "does not exist"})
        assert "title" not in tags
        assert "artists" not in tags
        assert "album" in tags
        assert "genres" in tags

    # noinspection PyTypeChecker,PyTestUnpassedFixture
    def test_to_tags_contains_no_properties(self, model: LocalTrack):
        tags = model.to_tags()
        assert "title" in tags
        assert all(value is not None for value in tags.values())

        assert all(key not in tags for key in IsLocalFile.model_fields)
        assert all(key not in tags for key in HasLength.model_fields)
        assert all(key not in tags for key in HasMutableURI.model_fields)

        # ignores properties even when explicitly given to include
        tags = model.to_tags(include={"path", "length"})
        assert all(key not in tags for key in IsLocalFile.model_fields)
        assert all(key not in tags for key in HasLength.model_fields)

    def test_update_and_replace(self, model: LocalTrack, file: mutagen.FileType, tags: dict[str, Any]):
        include = sample(list(set(tags) & set(LocalTrack.__tag_fields__)), k=4)
        exclude = sample(list(set(tags) & set(LocalTrack.__tag_fields__)), k=4)
        context = TagDumpContext()

        with (
            patch.object(LocalTrack, "to_tags", return_value=tags.copy()) as mock_to_tags,
            patch.object(file.__class__, "update") as mock_update,
        ):
            model.update(file, include=include, exclude=exclude, context=context, replace=True)

            mock_to_tags.assert_called_once_with(include=include, exclude=exclude, context=context)
            mock_update.assert_called_once_with(mock_to_tags.return_value)

    def test_update_no_replace(self, adapter: TypeAdapter[LocalTrack], file: mutagen.FileType, tags: dict[str, Any]):
        file.tags = dict(sample(list(tags.items()), k=4))
        expected = {k: v for k, v in tags.items() if k not in file.tags}
        model = adapter.validate_python(tags | dict(path=file.filename))

        with (
            patch.object(LocalTrack, "to_tags", return_value=tags.copy()),
            patch.object(file.__class__, "update") as mock_update,
        ):
            model.update(file, replace=False)
            mock_update.assert_called_once_with(expected)
