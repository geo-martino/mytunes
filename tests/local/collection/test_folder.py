from random import sample, choice

import pytest
from faker import Faker
from pydantic import ValidationError

from musify.local.collection.folder import Folder
from musify.local.item.album import LocalAlbum
from musify.local.item.track import LocalTrack
from tests.models.testers import NoUniqueKeyTester
from tests.utils import split_list


class TestFolder(NoUniqueKeyTester):
    @pytest.fixture
    def model(self, track: LocalTrack, tracks: list[LocalTrack]) -> Folder:
        parent = track.path.parent
        for tr in tracks:
            tr.path = parent.joinpath(tr.path.name)

        return Folder(name=parent.name, tracks=tracks)

    def test_folder_name_cannot_be_empty(self, tracks: list[LocalTrack], faker: Faker):
        with pytest.raises(ValidationError, match="no folders found in tracks"):
            Folder()

    def test_tracks_must_be_from_same_folder_when_no_name_given(self, tracks: list[LocalTrack], faker: Faker):
        assert len({track.folder for track in tracks}) > 1
        with pytest.raises(ValidationError, match="tracks are from different folders"):
            Folder(tracks=tracks)

    def test_get_folder_name_from_tracks(self, track: LocalTrack, tracks: list[LocalTrack]):
        parent = track.path.parent
        for tr in tracks:
            tr.path = parent.joinpath(tr.path.name)

        album = Folder(tracks=tracks)
        assert album.name == parent.name

    def test_filter_tracks_on_folder_name(self, tracks: list[LocalTrack]):
        expected = sample(tracks, k=len(tracks) // 2)
        parent = choice(expected).path.parent
        for track in expected:
            track.path = parent.joinpath(track.path.name)

        album = Folder(name=parent.name, tracks=tracks)
        assert sorted(album.tracks) == sorted(expected)

    def test_compilation(self, model: Folder):
        tracks_compilation, tracks_album, _ = split_list(model.tracks, 2, 5)
        compilation = LocalAlbum(name="Album 1", compilation=True)
        album = LocalAlbum(name="Album 2", compilation=False)

        for track in tracks_compilation:
            track.album = compilation
        for track in tracks_album:
            if track in tracks_compilation:
                continue
            track.album = album

        assert model.compilation is True

        for track in tracks_compilation:
            if track in tracks_album:
                continue
            track.album = album
        assert model.compilation is False

    def test_compilation_with_no_albums(self, model: Folder):
        for track in model.tracks:
            track.album = None
        assert model.compilation is False
