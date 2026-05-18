from abc import ABCMeta
from collections.abc import Iterator
from pathlib import PurePosixPath, Path, PureWindowsPath, PurePath, PosixPath
from random import choice
from typing import Literal

import pytest
from faker import Faker

from mytunes.core.properties.file import IsLocalFile
from mytunes.core.properties.path import PathMapper, PathParentMapper, PathModelMapper
from tests.testers import BaseModelTester

SYSTEM_TYPES = Literal["linux", "windows"]


def _generate_file_paths(
        faker: Faker, system: SYSTEM_TYPES = None, count: int = 20
) -> Iterator[PurePath]:
    if system is None:
        system: SYSTEM_TYPES = "linux" if isinstance(Path.home(), PosixPath) else "windows"

    path_iter = (
        Path(faker.file_path(depth=faker.random_int(4, 10), category="audio", file_system_rule=system))
        for _ in range(count)
    )
    return map(PurePosixPath, path_iter) if system == "linux" else map(PureWindowsPath, path_iter)


def _generate_directory_paths(
        faker: Faker, system: SYSTEM_TYPES = None, count: int = 20
) -> Iterator[PurePath]:
    return (path.parent for path in _generate_file_paths(faker, system=system, count=count))


class PathMapperTester(BaseModelTester, metaclass=ABCMeta):
    @staticmethod
    def test_checks_existence_on_non_existing_files(model: PathMapper, faker: Faker):
        files = [choice([str(path), IsLocalFile(path=Path(path))]) for path in _generate_file_paths(faker)]

        assert not any(model.serialise(file, check_existence=True) for file in files)
        assert not any(model.deserialise(file, check_existence=True) for file in files)
        assert not model.serialise_many(files, check_existence=True)
        assert not model.deserialise_many(files, check_existence=True)

    @staticmethod
    def test_checks_existence_on_existing_files(model: PathMapper, faker: Faker, tmp_path: Path):
        files = [choice([str(path), IsLocalFile(path=Path(path))]) for path in _generate_file_paths(faker)]
        existing_files = [
            tmp_path.with_name(faker.file_name(category="audio")) for _ in range(faker.random_int(5, 8))
        ]
        for path in existing_files:
            path.touch(exist_ok=True)

        result = set(model.serialise_many(files + existing_files, check_existence=True))
        assert result == set(map(str, existing_files))

    @staticmethod
    def test_mapping_from_model(model: PathMapper, faker: Faker):
        expected = list(map(str, _generate_file_paths(faker)))
        files = [choice([path, IsLocalFile(path=Path(path))]) for path in expected]

        assert [model.serialise(file, check_existence=False) for file in files] == expected
        assert model.serialise_many(files, check_existence=False) == expected
        assert [model.deserialise(file, check_existence=False) for file in files] == expected
        assert model.deserialise_many(files, check_existence=False) == expected


class TestPathModelMapper(PathMapperTester):
    @pytest.fixture
    def model(self, faker: Faker) -> PathModelMapper:
        return PathModelMapper()


class TestPathParentMapper(PathMapperTester):
    @pytest.fixture
    def model(self, faker: Faker) -> PathParentMapper:
        parents = list(_generate_directory_paths(faker, "windows"))
        others = list(_generate_directory_paths(faker, "linux"))

        parent_serialise = {parent: faker.random_element(others) for parent in parents}
        parent_serialise = {str(k): str(v) for k, v in parent_serialise.items()}

        parent_deserialise = {parent: faker.random_element(parents) for parent in others}
        parent_deserialise = {str(k): str(v) for k, v in parent_deserialise.items()}

        return PathParentMapper(parent_serialise=parent_serialise, parent_deserialise=parent_deserialise)

    @pytest.fixture
    def paths(self, model: PathParentMapper, faker: Faker) -> list[str]:
        parents = map(Path, model.parent_serialise.keys())
        return [str(parent.joinpath(faker.file_name(category="audio"))) for parent in parents]

    def test_mapping(self, model: PathParentMapper, faker: Faker):
        linux = PurePosixPath(
            faker.file_path(depth=faker.random_int(4, 10), category="audio", file_system_rule="linux")
        )

        windows = PureWindowsPath(
            faker.file_path(depth=faker.random_int(4, 10), category="audio", file_system_rule="windows")
        )
        windows = windows.parent.joinpath(linux.name)

        other = PurePosixPath(
            faker.file_path(depth=faker.random_int(4, 10), category="audio", file_system_rule="linux")
        )
        other = other.parent.joinpath(linux.name)

        model.parent_serialise = {str(linux.parent): str(windows.parent)}
        model.parent_deserialise = {str(windows.parent): str(other.parent)}

        serialised = model.serialise(str(linux), check_existence=False)
        assert serialised == str(windows)

        expected = other.parent.joinpath(linux.name)
        assert model.deserialise(str(serialised), check_existence=False) == str(expected)

    def test_mapping_many(self, model: PathParentMapper, faker: Faker):
        parents = list(_generate_directory_paths(faker, "windows"))
        others = list(_generate_directory_paths(faker, "linux"))
        paths = [str(parent.joinpath(faker.file_name(category="audio"))) for parent in parents]

        # ensure reversible
        mapping = dict(zip(map(str, parents), map(str, others)))
        mapping_reversed = dict(list(item[::-1]) for item in reversed(list(mapping.items())))
        assert mapping == dict(list(item[::-1]) for item in reversed(list(mapping_reversed.items())))

        model.parent_serialise = mapping
        model.parent_deserialise = mapping_reversed

        serialised = model.serialise_many(paths, check_existence=False)
        assert serialised != paths
        for path in serialised:
            assert any(path.startswith(parent) for parent in model.parent_serialise.values())
            assert all(not path.startswith(parent) for parent in model.parent_serialise)
            assert "\\" not in path

        assert model.deserialise_many(serialised, check_existence=False) == paths
