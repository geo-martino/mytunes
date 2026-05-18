from abc import ABCMeta
from collections.abc import Iterable
from pathlib import Path

import pytest

from mytunes.core.properties.path import PathParentMapper
from mytunes.local._collection.playlist import LocalPlaylist
from mytunes.result import Result
from tests.testers import UniqueKeyTester


class LocalPlaylistTester(UniqueKeyTester, metaclass=ABCMeta):
    @pytest.fixture
    def path_mapper(self, tmp_path: Path) -> PathParentMapper:
        """Creates a basic PathParentMapper for the given tracks."""
        parent = "folder/"
        return PathParentMapper(
            serialise={parent: str(tmp_path)},
            deserialise={str(tmp_path): parent},
        )

    @staticmethod
    async def assert_save_to_new_file(model: LocalPlaylist, path: Path) -> None:
        """Asserts that saving to a new file works as expected."""
        assert model.path.is_file()
        assert model.modified_at is not None

        model.name = "New Playlist"
        assert model.path == path
        assert path.is_file()
        assert model.modified_at is not None

        await model.save(dry_run=False)

        assert model.path == path.with_stem("New Playlist")
        assert not path.is_file()
        assert model.path.is_file()
        assert model.modified_at is not None

    @staticmethod
    def assert_paths_are_mapped(paths: Iterable[str | Path]) -> None:
        """Asserts that all paths are correctly mapped using the PathParentMapper."""
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

        assert await model.save(dry_run=True) == await model.save(dry_run=False)
        assert model.modified_at > original_dt_modified

    @staticmethod
    def assert_model_file_does_not_exist(model: LocalPlaylist) -> None:
        """Asserts that the model's file does not exist."""
        assert not model.path.is_file()
        assert model.modified_at is None

    @staticmethod
    def assert_model_file_exists(model: LocalPlaylist) -> None:
        """Asserts that the model's file does not exist."""
        assert model.path.is_file()
        assert model.modified_at is not None
