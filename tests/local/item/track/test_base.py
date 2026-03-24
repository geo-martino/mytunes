from argparse import Namespace
from collections.abc import Generator
from datetime import date
from pathlib import Path
from random import choice, sample
from typing import Any, Sequence
from unittest.mock import patch, AsyncMock, Mock, MagicMock

import mutagen
import mutagen.wave
import pytest
from faker import Faker
from pydantic import TypeAdapter
from pytest_mock import MockerFixture

from musify.local.exception import TagError
from musify.local.item.artist import LocalArtist
from musify.local.item.track import LocalTrack, TagContext, HasLocalTracks
from musify.models.properties.file import IsLocalFile
from musify.models.properties.image import ImageFile
from musify.models.properties.length import HasLength
from musify.models.properties.uri import HasMutableURI, URI
from tests.models.testers import UniqueKeyTester
from tests.utils import assert_validator_skips, SimpleURI, split_list


class TestLocalTrack(UniqueKeyTester):
    @pytest.fixture
    def model(self, tags: dict[str, Any], faker: Faker) -> LocalTrack:
        uri = SimpleURI.from_id(
            faker.random_int(int(10e9), int(10e10)), kind=LocalTrack.type
        )
        return LocalTrack(**tags, uri=uri, path=faker.file_path())

    @pytest.fixture
    def uri(self, faker: Faker) -> SimpleURI:
        return SimpleURI.from_id(
            faker.random_int(int(10e9), int(10e10)), kind=LocalTrack.type
        )

    @pytest.fixture
    def tags(self, uri: URI, image_files: list[ImageFile]) -> dict[str, Any]:
        sep = choice(LocalTrack._tag_sep)
        return {
            "name": ["Sleepwalk My Life Away"],
            "artists": ["Metallica"],
            "album": ["72 Seasons"],
            "album_artist": ["Metallica and friends"],
            "genres": ["Hard Rock", "Metal" + sep + "Rock", "Thrash Metal"],
            "track": ["04"],
            "disc": ["1/2"],
            "bpm": ["124.931"],
            "key": ["B"],
            "released_at": ["2023-04-14"],
            "comments": [str(uri)],
            "compilation": ["1"],
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

    @pytest.fixture
    def include_tags(self, tags: dict[str, Any], faker: Faker) -> Sequence[str]:
        return faker.random_elements(list(set(tags) & set(LocalTrack.__tag_fields__)))

    @pytest.fixture
    def exclude_tags(self, tags: dict[str, Any], faker: Faker) -> Sequence[str]:
        return faker.random_elements(list(set(tags) & set(LocalTrack.__tag_fields__)))

    @pytest.fixture
    def context(self) -> TagContext:
        return TagContext()

    @pytest.fixture
    def mock_load_file(self, file: mutagen.FileType) -> Generator[Mock, None, None]:
        with patch.object(LocalTrack, "load_file", return_value=file) as mock_load:
            yield mock_load

    ###########################################################################
    ## Utility Methods
    ###########################################################################
    async def test_from_path(self, file: mutagen.FileType, mock_load_file: Mock):
        model = await LocalTrack.from_path(file.filename)
        mock_load_file.assert_called_once_with(file.filename)
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

    def test_serialize_images_skips(self, model: LocalTrack, context: TagContext):
        # skips when not serializing by alias
        info = Namespace(by_alias=False, context=None, mode="python")
        # noinspection PyTypeChecker
        results = model._serialize_images(model.images, info=info)
        assert results is model.images

        # skips when loaded_images are not available
        info = Namespace(by_alias=True, context=context, mode="python")
        # noinspection PyTypeChecker
        results = model._serialize_images(model.images, info=info)
        assert not results

    def test_from_tags(self, uri: URI, image_files: list[ImageFile], tags: dict[str, Any], faker: Faker):
        context = TagContext(remote_source=uri.source, map_uri_to_tag="comments")
        model = LocalTrack.model_validate(dict(**tags, path=faker.file_path()), context=context)

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
        assert model.comments == tags["comments"]

        assert model.source == uri.source
        assert model.uris == [uri]
        assert model.uri == uri

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
        tags: dict[str, Any],
        mock_load_file: Mock,
    ):
        expected = adapter.validate_python(tags | dict(path=file.filename))

        await model.load()

        mock_load_file.assert_called_once()
        assert model is not expected
        assert model.name == expected.name
        assert model.artist == expected.artist
        assert model.album.name == expected.album.name
        assert model.genre == expected.genre

    async def test_save(self, model: LocalTrack, file: mutagen.FileType, faker: Faker):
        with patch.object(mutagen.FileType, "save") as mock_save:
            await model.save(file)
            mock_save.assert_called_once()

    def test_clear_all_tags(self, file: mutagen.FileType, faker: Faker):
        expected = set(file.tags.keys())
        result = LocalTrack.clear(file)
        assert set(result) == expected & set(LocalTrack.__tag_fields__)

    def test_clear_selected_tags(self, file: mutagen.FileType, include_tags: Sequence[str], faker: Faker):
        result = LocalTrack.clear(file, include=include_tags)
        assert set(result) == set(include_tags)

    def test_clear_selected_tags_with_exclude(
            self,
            file: mutagen.FileType,
            include_tags: Sequence[str],
            exclude_tags: Sequence[str],
            faker: Faker,
    ):
        result = LocalTrack.clear(file, include=include_tags, exclude=exclude_tags)
        assert set(result) == set(t for t in include_tags if t not in exclude_tags)

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
        tags = model.to_tags(include={"name", "album", "album_artist", "compilation"}, exclude={"name"})
        assert "title" not in tags
        assert "album_artist" in tags
        assert "compilation" in tags
        assert "comments" not in tags

        tags = model.to_tags(exclude={"name", "comments"})
        assert "title" not in tags
        assert "album" in tags
        assert "album_artist" in tags
        assert "compilation" in tags
        assert "comments" not in tags

        with pytest.raises(TagError):
            model.to_tags(exclude={"name", "does not exist"})

    # noinspection PyTypeChecker,PyTestUnpassedFixture
    def test_to_tags_contains_no_properties(self, model: LocalTrack):
        tags = model.to_tags()
        assert "title" in tags
        assert all(value is not None for value in tags.values())

        assert all(key not in tags for key in IsLocalFile.model_fields)
        assert all(key not in tags for key in HasLength.model_fields)
        assert all(key not in tags for key in HasMutableURI.model_fields)

        with pytest.raises(TagError):
            model.to_tags(include={"path"})
        with pytest.raises(TagError):
            model.to_tags(include={"length"})

    @pytest.fixture
    def mock_to_tags(self, tags: dict[str, Any]) -> Generator[Mock, None, None]:
        with patch.object(LocalTrack, "to_tags", return_value=tags.copy()) as mock_to_tags:
            yield mock_to_tags

    def test_update_and_replace(
            self,
            model: LocalTrack,
            file: mutagen.FileType,
            include_tags: Sequence[str],
            exclude_tags: Sequence[str],
            context: TagContext,
            mock_to_tags: Mock,
            mocker: MockerFixture,
    ):
        mock_update = mocker.spy(file, "update")

        model.update(file, include=include_tags, exclude=exclude_tags, context=context, replace=True)

        mock_to_tags.assert_called_once_with(include=include_tags, exclude=exclude_tags, context=context)
        mock_update.assert_called_once_with(mock_to_tags.return_value)

    def test_update_no_replace(
            self,
            adapter: TypeAdapter[LocalTrack],
            file: mutagen.FileType,
            tags: dict[str, Any],
            mock_to_tags: Mock,
            mocker: MockerFixture,
    ):
        file.tags = dict(sample(list(tags.items()), k=4))
        expected = {k: v for k, v in tags.items() if k not in file.tags}
        model = adapter.validate_python(tags | dict(path=file.filename))

        mock_update = mocker.spy(file, "update")

        model.update(file, replace=False)

        mock_to_tags.assert_called_once_with(include=(), exclude=(), context=None)
        mock_update.assert_called_once_with(expected)

    @pytest.fixture
    def merge_tracks(self, tracks: list[LocalTrack], faker: Faker) -> tuple[LocalTrack, LocalTrack]:
        track, other = faker.random_elements(tracks, length=2)

        other.name = faker.sentence()
        other.artists = faker.words()
        other.uri = SimpleURI.from_id(faker.random_int(int(10e9), int(10e10)), kind=LocalTrack.type)

        track.released_at = None
        other.released_at = faker.date()

        track.comments = faker.words()
        other.comments = track.comments + faker.words()

        assert track.name != other.name
        assert track.artist != other.artist
        assert track.album == other.album
        assert track.genres == other.genres
        assert track.released_at != other.released_at
        assert track.comments != other.comments
        assert track.uri != other.uri

        return track, other

    def test_merge_no_replace(self, merge_tracks: tuple[LocalTrack, LocalTrack]):
        track, other = merge_tracks

        expected = {
            "released_at": other.released_at,
        }

        result = track.merge(other, include={"name", "artists", "released_at"})
        assert result == expected

        assert track.name != other.name  # doesn't replace because it was already set
        assert track.artist != other.artist  # doesn't replace because it was already set
        assert track.album == other.album
        assert track.genres == other.genres
        assert track.released_at == other.released_at
        assert track.comments != other.comments

    def test_merge_with_replace(self, merge_tracks: tuple[LocalTrack, LocalTrack]):
        track, other = merge_tracks

        expected = {
            "artists": other.artists,
            "released_at": other.released_at,
            "comments": other.comments,
        }

        result = track.merge(other, replace=True, exclude={"name"})
        assert result == expected

        assert track.name != other.name
        assert track.artist == other.artist
        assert track.album == other.album
        assert track.genres == other.genres
        assert track.released_at == other.released_at
        assert track.comments == other.comments
        assert track.uri != other.uri  # uri field is always ignored

    ###########################################################################
    ## HasLocalTracks
    ###########################################################################
    @pytest.fixture
    def replace_tags(self, tags: dict[str, Any], faker: Faker) -> bool:
        return faker.boolean()

    @pytest.fixture
    def mock_load(self, file: mutagen.FileType, tracks: list[LocalTrack]) -> Generator[Mock, None, None]:
        with patch.object(LocalTrack, "load", return_value=file, new_callable=AsyncMock) as mock_load:
            yield mock_load
            assert mock_load.call_count == len(tracks)

    @pytest.fixture
    def mock_update(
            self,
            tracks: list[LocalTrack],
            file: mutagen.FileType,
            tags: dict[str, Any],
            include_tags: Sequence[str],
            exclude_tags: Sequence[str],
            context: TagContext,
            replace_tags: bool,
            faker: Faker,
    ) -> Generator[tuple[Mock, list[dict[str, Any]]], None, None]:
        expected = []

        def _random_tags(*_, **__) -> dict[str, Any]:
            expected_tags = dict(faker.random_elements(list(tags.items())))
            expected.append(expected_tags)
            return expected_tags

        with patch.object(LocalTrack, "update", side_effect=_random_tags) as mock_update:
            yield mock_update, expected

            assert mock_update.call_count == len(tracks)
            mock_update.assert_any_call(
                file, include=include_tags, exclude=exclude_tags, context=context, replace=replace_tags
            )

    @pytest.fixture
    def mock_save(self) -> Generator[Mock, None, None]:
        with patch.object(LocalTrack, "save") as mock_save:
            yield mock_save

    async def test_save_tracks_dry_run(
            self,
            tracks: list[LocalTrack],
            include_tags: Sequence[str],
            exclude_tags: Sequence[str],
            context: TagContext,
            replace_tags: bool,
            mock_load: Mock,
            mock_update: tuple[Mock, list[dict[str, Any]]],
            mock_save: Mock,
    ):
        model = HasLocalTracks(tracks=tracks)
        mock_update, expected = mock_update

        results = await model.save_tracks(
            include=include_tags, exclude=exclude_tags, context=context, replace=replace_tags, dry_run=True
        )
        assert set(results.keys()) == {track.path for track in tracks}
        assert all(t in results.values() for t in expected)

        mock_save.assert_not_called()

    async def test_save_tracks(
            self,
            tracks: list[LocalTrack],
            include_tags: Sequence[str],
            exclude_tags: Sequence[str],
            context: TagContext,
            replace_tags: bool,
            mock_load: Mock,
            mock_update: tuple[Mock, list[dict[str, Any]]],
            mock_save: Mock,
    ):
        model = HasLocalTracks(tracks=tracks)
        mock_update, expected_tags = mock_update

        results = await model.save_tracks(
            include=include_tags, exclude=exclude_tags, context=context, replace=replace_tags, dry_run=False
        )
        assert set(results.keys()) == {track.path for track in tracks}
        assert all(t in results.values() for t in expected_tags)

        assert mock_save.call_count == sum(1 for t in expected_tags if t)

    def test_merge_tracks(
            self,
            tracks: list[LocalTrack],
            include_tags: Sequence[str],
            exclude_tags: Sequence[str],
            replace_tags: bool,
            mocker: MockerFixture,
            faker: Faker,
    ):
        tracks, others, overlap = split_list(tracks, 2, overlap=5)
        model = HasLocalTracks(tracks=tracks)
        expected = []

        def _generate_tags(*_, **__) -> dict[str, Any]:
            tags = faker.pydict()
            expected.append(tags)
            return tags

        with patch.object(LocalTrack, "merge", side_effect=_generate_tags) as mock_merge:
            result = model.merge_tracks(others, include=include_tags, exclude=exclude_tags, replace=replace_tags)
            assert result.keys() == {track.path for track in overlap}
            assert list(result.values()) == expected

            assert mock_merge.call_count == len(overlap)
            assert [arg for call in mock_merge.call_args_list for arg in call.args] == overlap
            for call in mock_merge.call_args_list:
                assert call.kwargs == dict(include=include_tags, exclude=exclude_tags, replace=replace_tags)

    @pytest.fixture
    def restore_tracks(self, tracks: list[LocalTrack], faker: Faker) -> list[LocalTrack]:
        for track in tracks:
            track.uri = SimpleURI.from_id(faker.pystr(22, 22), kind=LocalTrack.type)
        return tracks

    def test_restore_tracks_on_field(self, restore_tracks: list[LocalTrack], faker: Faker):
        new_title = "brand new title"
        new_artist = "brand new artist"

        backup: list[dict[str, Any]] = [track.model_dump() for track in restore_tracks]
        for track in backup:
            track["name"] = new_title

        model = HasLocalTracks(tracks=restore_tracks)
        model.restore_tracks(backup)

        for track in model.tracks:
            assert track.name == new_title
            assert track.artist != new_artist

    def test_restore_tracks_on_fields(self, restore_tracks: list[LocalTrack], faker: Faker):
        new_title = "brand new title"
        new_artist = "brand new artist"

        backup: list[dict[str, Any]] = [track.model_dump() for track in restore_tracks]
        for track in backup:
            track["name"] = new_title
            track["artists"] = [new_artist]

        model = HasLocalTracks(tracks=restore_tracks)
        model.restore_tracks({Path(track["path"]): track for track in backup})

        for track in model.tracks:
            assert track.name == "brand new title"
            assert track.artist == new_artist
