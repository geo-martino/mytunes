from pathlib import Path

import mutagen
import mutagen.wave
import pytest
from faker import Faker

from musify.models.properties.audio import IsAudioFile
from musify.models.properties.file import IsLocalFile
from tests.models.testers import MusifyResourceTester


class LocalAudioFile(IsLocalFile, IsAudioFile):
    pass


class TestIsAudioFile(MusifyResourceTester):

    @pytest.fixture
    def model(self, faker: Faker, tmp_path: Path) -> IsAudioFile:
        return LocalAudioFile(path=tmp_path.joinpath(faker.file_name(extension="wav")))

    @pytest.fixture
    def file(self, faker: Faker, tmp_path: Path) -> mutagen.FileType:
        path = tmp_path.joinpath(faker.file_name(category="audio"))

        file = mutagen.FileType()
        file.filename = str(path)
        file.tags = {}

        stream_info = mutagen.wave.WaveStreamInfo.__new__(mutagen.wave.WaveStreamInfo)
        stream_info.length = faker.random_int() / 100
        stream_info.channels = 2
        stream_info.bitrate = 320000
        stream_info.sample_rate = 44100
        stream_info.bits_per_sample = 16
        file.info = stream_info

        return file

    def test_extract_tags_from_mutagen(self, file: mutagen.FileType):
        result = IsAudioFile.extract_tags_from_mutagen(file)
        assert result == dict(
            length=file.info.length,
            channels=file.info.channels,
            bit_rate=file.info.bitrate / 1000,
            bit_depth=file.info.bits_per_sample,
            sample_rate=file.info.sample_rate / 1000,
        )
