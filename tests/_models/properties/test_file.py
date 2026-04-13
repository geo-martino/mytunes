from pathlib import Path

import mutagen
import pytest
from faker import Faker
from mytunes._models.properties.file import IsLocalFile
from mytunes.exception import MyTunesTypeError
from tests.testers import BaseModelTester


class TestIsLocalFile(BaseModelTester):
    @pytest.fixture
    def model(self, faker: Faker) -> IsLocalFile:
        return IsLocalFile(path=Path(faker.file_path()))

    def test_get_ext_from_input_fails(self):
        with pytest.raises(MyTunesTypeError):
            IsLocalFile._get_ext_from_input(123)

    def test_get_ext_from_input(self, faker: Faker):
        path = Path(faker.file_path())
        expected = path.suffix.lstrip(".").casefold()

        assert IsLocalFile._get_ext_from_input(str(path)) == expected
        assert IsLocalFile._get_ext_from_input(path) == expected
        assert IsLocalFile._get_ext_from_input(dict(path=path)) == expected
        assert IsLocalFile._get_ext_from_input(IsLocalFile(path=path)) == expected

    def test_map_path(self, faker: Faker):
        path = Path(faker.file_path())
        value = str(path) if faker.boolean() else path
        model = IsLocalFile.model_validate(value)
        assert model.path == path

    def test_extract_tags_from_mutagen(self, model: IsLocalFile, faker: Faker):
        file = mutagen.FileType()
        file.filename = str(model.path)

        data = IsLocalFile._extract_tags_from_mutagen(file)
        assert data == dict(path=str(model.path))

    def test_rename_when_path_not_exists(self, model: IsLocalFile, faker: Faker):
        assert not model.path.exists()

        new_filename = faker.file_name(category="audio")
        model.filename = new_filename

        assert model.path.stem == new_filename
        assert not model.path.exists()

    def test_rename_when_path_exists(self, model: IsLocalFile, faker: Faker, tmp_path: Path):
        model.path = tmp_path.joinpath(faker.file_name(category="audio"))
        model.path.write_text("test")
        assert model.path.exists()

        new_filename = faker.file_name(category="audio")
        model.filename = new_filename

        assert model.path.stem == new_filename
        assert model.path.exists()
