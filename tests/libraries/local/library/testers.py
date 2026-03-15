from abc import ABCMeta
from pathlib import Path
from typing import Any

from musify.libraries.local.library import LocalLibrary
from musify.libraries.local.playlist.m3u import SyncResultM3U
from musify.libraries.local.playlist.xautopf import SyncResultXAutoPF
from tests.libraries.core.object import LibraryTester
from tests.libraries.local.track.testers import LocalCollectionTester


class LocalLibraryTester(LibraryTester, LocalCollectionTester, metaclass=ABCMeta):

    @staticmethod
    async def test_save_playlists(library: LocalLibrary):
        playlists = [pl for pl in library.playlists.values() if len(pl) > 0]
        for playlist in playlists:
            playlist.pop()

        results = await library.save_playlists(dry_run=True)

        assert len(results) == len(library.playlists)
        for pl, result in results.items():
            if pl not in playlists:
                continue

            if isinstance(result, SyncResultM3U):
                assert result.removed == 1
            elif isinstance(result, SyncResultXAutoPF):
                assert result.start - result.final == 1

    @staticmethod
    def test_restore_tracks(library: LocalLibrary):
        new_title = "brand new title"
        new_artist = "brand new artist"

        for track in library:
            assert track.title != "brand new title"
            assert track.artist != new_artist

        backup: dict[str, Any] = library.json()
        for track in backup["tracks"]:
            track["title"] = new_title

        library.restore_tracks(backup)
        for track in library:
            assert track.title == "brand new title"
            assert track.artist != new_artist

        for track in backup["tracks"]:
            track["artist"] = new_artist

        library.restore_tracks({Path(track["path"]): track for track in backup["tracks"]})
        for track in library:
            assert track.title == "brand new title"
            assert track.artist == new_artist
