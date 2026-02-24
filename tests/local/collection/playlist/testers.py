from abc import ABCMeta
from collections.abc import Iterable
from pathlib import Path

import pytest

from musify.local.collection.playlist import LocalPlaylist
from musify.models.properties.file import PathStemMapper
from musify.processors_new import Result
from tests.models.testers import UniqueKeyTester


class LocalPlaylistTester(UniqueKeyTester, metaclass=ABCMeta):
    @pytest.fixture
    def path_mapper(self, tmp_path: Path) -> PathStemMapper:
        """Creates a basic PathStemMapper for the given tracks."""
        return PathStemMapper(stem_map={"folder/": str(tmp_path)})

    @staticmethod
    async def assert_save_to_new_file(model: LocalPlaylist, path: Path) -> None:
        """Asserts that saving to a new file works as expected."""
        assert model.path.is_file()
        assert model.modified_at is not None
        assert model.created_at is not None

        model.name = "New Playlist"
        assert model.path == path
        assert path.is_file()
        assert model.modified_at is not None
        assert model.created_at is not None

        await model.save(dry_run=False)

        assert model.path == path.with_stem("New Playlist")
        assert not path.is_file()
        assert model.path.is_file()
        assert model.modified_at is not None
        assert model.created_at is not None

    @staticmethod
    def assert_paths_are_mapped(paths: Iterable[str | Path]) -> None:
        """Asserts that all paths are correctly mapped using the PathStemMapper."""
        assert all(str(path).startswith("folder/") for path in paths)

    @classmethod
    async def assert_save_dry_run(cls, model: LocalPlaylist) -> Result:
        """Asserts that saving in dry-run mode does not create the file."""
        cls.assert_model_file_does_not_exist(model)
        result = await model.save(dry_run=True)
        cls.assert_model_file_does_not_exist(model)
        return result

    @classmethod
    async def assert_save(cls, model: LocalPlaylist) -> Result:
        """Asserts that saving in dry-run mode does not create the file."""
        cls.assert_model_file_does_not_exist(model)
        result = await model.save(dry_run=False)
        cls.assert_model_file_exists(model)
        return result

    @classmethod
    async def assert_save_to_existing_file(cls, model: LocalPlaylist) -> None:
        """Asserts that saving to an existing file works as expected."""
        cls.assert_model_file_exists(model)
        original_dt_modified = model.modified_at
        # original_dt_created = model.created_at

        assert await model.save(dry_run=True) == await model.save(dry_run=False)

        # TODO: these assertions fail on GitHub actions but not locally, why?
        assert model.modified_at > original_dt_modified
        # assert model.created_at == original_dt_created  # TODO: doesn't work?

    @staticmethod
    def assert_model_file_does_not_exist(model: LocalPlaylist) -> None:
        """Asserts that the model's file does not exist."""
        assert not model.path.is_file()
        assert model.modified_at is None
        assert model.created_at is None

    @staticmethod
    def assert_model_file_exists(model: LocalPlaylist) -> None:
        """Asserts that the model's file does not exist."""
        assert model.path.is_file()
        assert model.modified_at is not None
        assert model.created_at is not None
