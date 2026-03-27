import re
from abc import ABCMeta, abstractmethod
from itertools import batched
from pathlib import Path
from random import randrange, choice, sample

import pytest
from pytest_mock import MockerFixture

from musify.libraries.collection import BasicCollection
from musify.libraries.local.track import LocalTrack
from musify.libraries.remote.core.object import RemotePlaylist
from musify.libraries.remote.core.types import RemoteObjectType
from musify.processors.check import RemoteItemChecker
from tests.conftest import LogCapturer
from tests.libraries.local.track.utils import random_track, random_tracks
from tests.libraries.remote.core.processors.utils import patch_input
from tests.libraries.remote.core.utils import RemoteMock
from tests.libraries.remote.spotify.utils import random_uri, random_uris
from tests.testers import PrettyPrinterTester
from tests.utils import path_token, random_str


class RemoteItemCheckerTester(PrettyPrinterTester, metaclass=ABCMeta):
    """Run generic tests for :py:class:`RemoteItemSearcher` implementations."""

    @pytest.fixture
    def obj(self, checker: RemoteItemChecker) -> RemoteItemChecker:
        return checker

    @abstractmethod
    def checker(self, *args, **kwargs) -> RemoteItemChecker:
        """Yields a valid :py:class:`RemoteItemChecker` for the current remote source as a pytest.fixture."""
        raise NotImplementedError

    @abstractmethod
    def playlists(self, *args, **kwargs) -> list[RemotePlaylist]:
        """Yields a list of fully extended user playlist objects from the api_mock as a pytest.fixture."""
        raise NotImplementedError

    @pytest.fixture
    def collections(self, playlists: list[RemotePlaylist]) -> list[BasicCollection]:
        """Yields many valid :py:class:`BasicCollection` of :py:class:`LocalTrack` as a pytest.fixture."""
        count = randrange(6, len(playlists))
        return [BasicCollection(name=random_str(30, 50), items=random_tracks()) for _ in range(count)]

    @staticmethod
    @pytest.fixture
    async def setup_playlist_collection(
            checker: RemoteItemChecker, playlists: list[RemotePlaylist]
    ) -> tuple[RemotePlaylist, BasicCollection]:
        """Setups up checker, playlist, and collection for testing match_to_remote functionality"""
        pl = choice(playlists)
        assert len(pl) > 10
        assert len({item.uri for item in pl}) == len(pl)  # all unique tracks

        collection = BasicCollection(name="test", items=pl.tracks.copy())
        checker._playlist_originals = {collection.name: pl}
        checker._playlist_check_collections = {collection.name: collection}

        return pl, collection

    # noinspection PyProtectedMember
    @staticmethod
    @pytest.fixture
    def setup_empty_playlist_originals(checker: RemoteItemChecker) -> None:
        """Clears all items in the originals playlist to ensure simpler checks on matching"""
        for pl in checker._playlist_originals.values():
            pl.clear()

    ###########################################################################
    ## Utilities
    ###########################################################################
    @pytest.fixture(params=[path_token])
    def token_file_path(self, path: Path) -> Path:
        """Yield the temporary path for the token JSON file"""
        return path

    @staticmethod
    async def test_make_temp_playlist(checker: RemoteItemChecker, api_mock: RemoteMock, token_file_path: Path):
        # force auth test to fail and reload from token
        checker.api.handler.authoriser.response.replace({})
        checker.api.handler.authoriser.response.file_path = token_file_path

        collection = BasicCollection(name=random_str(30, 50), items=random_tracks())
        for item in collection:
            item.uri = None

        # does nothing when no URIs to add
        await checker._create_playlist(collection=collection)
        assert not checker._playlist_originals
        assert not checker._playlist_check_collections
        api_mock.assert_not_called()

        for item in collection:
            item.uri = random_uri()

        await checker._create_playlist(collection=collection)
        assert checker.api.handler.authoriser.response
        assert collection.name in checker._playlist_originals
        assert checker._playlist_check_collections[collection.name] == collection
        assert api_mock.total_requests >= 2

    @staticmethod
    async def test_delete_temp_playlists(
            checker: RemoteItemChecker,
            collections: list[BasicCollection],
            playlists: list[RemotePlaylist],
            api_mock: RemoteMock,
            token_file_path: Path
    ):
        # force auth test to fail and reload from token
        checker.api.handler.authoriser.response.replace({})
        checker.api.handler.authoriser.response.file_path = token_file_path

        for pl in sample(playlists, k=len(playlists) // 2):
            pl.clear()
        playlists_to_delete = [pl for pl in playlists if len(pl) == 0]
        playlists_to_keep = [pl for pl in playlists if pl not in playlists_to_delete]

        assert playlists_to_delete
        assert playlists_to_keep

        checker._playlist_originals = {pl.name: pl for pl in playlists}
        checker._playlist_check_collections = {collection.name: collection for collection in collections}

        await checker._delete_playlists()
        assert checker.api.handler.authoriser.response  # re-authorised
        assert not checker._playlist_originals
        assert not checker._playlist_check_collections

        for playlist in playlists_to_delete:
            assert len(await api_mock.get_requests(method="DELETE", url=re.compile(str(playlist.url)))) == 1
        for playlist in playlists_to_keep:
            assert not await api_mock.get_requests(method="DELETE", url=re.compile(str(playlist.url)))
            # there will be no items to add so this won't work in tests
            # assert await api_mock.get_requests(method="POST", url=re.compile(str(playlist.url)))

    @staticmethod
    async def test_finalise(checker: RemoteItemChecker):

        checker._started = True
        checker._remaining.extend(random_tracks(3))
        checker._switched.extend(random_tracks(2))

        checker._final_switched = switched = random_tracks(1)
        checker._final_unavailable = unavailable = random_tracks(2)
        checker._final_skipped = skipped = random_tracks(3)

        result = await checker.close()

        assert not checker._started
        assert not checker._remaining
        assert not checker._switched
        assert not checker._final_switched
        assert not checker._final_unavailable
        assert not checker._final_skipped

        assert result.switched == switched
        assert result.unavailable == unavailable
        assert result.skipped == skipped

    ###########################################################################
    ## ``pause`` step
    ###########################################################################
    @staticmethod
    async def test_pause_1(
            checker: RemoteItemChecker,
            setup_playlist_collection: tuple[RemotePlaylist, BasicCollection],
            mocker: MockerFixture,
            api_mock: RemoteMock,
            log_capturer: LogCapturer,
    ):
        pl, collection = setup_playlist_collection
        patch_input(["h", collection.name, pl.uri], mocker=mocker)

        with log_capturer(loggers=[checker.logger, checker.api.logger]):
            await checker._pause(page=1, total=1)
        mocker.stopall()

        # help text printed initially and reprinted on request
        assert log_capturer.text.count("Enter one of the following") == 2
        assert "Input not recognised" not in log_capturer.text
        assert f"Showing items originally added to {collection.name}" in log_capturer.text  # <Name of playlist> entered
        assert f"Showing tracks for playlist: {pl.name}" in log_capturer.text

        pl_pages = api_mock.calculate_pages(limit=20, total=len(pl))
        assert len(await api_mock.get_requests(method="GET", url=re.compile(str(pl.url)))) == pl_pages + 1

        assert not checker._skip
        assert not checker._quit

    @staticmethod
    async def test_pause_2(
            checker: RemoteItemChecker,
            mocker: MockerFixture,
            api_mock: RemoteMock,
            log_capturer: LogCapturer,
    ):
        patch_input([random_str(10, 20), "u", "s"], mocker=mocker)

        with log_capturer(loggers=checker.logger):
            await checker._pause(page=1, total=1)
        mocker.stopall()

        assert log_capturer.text.count("Enter one of the following") == 1
        assert log_capturer.text.count("Input not recognised") == 2
        assert "Showing items originally added to" not in log_capturer.text
        assert "Showing tracks for playlist" not in log_capturer.text

        api_mock.assert_not_called()

        assert checker._skip
        assert not checker._quit

    @staticmethod
    async def test_pause_3(
            checker: RemoteItemChecker,
            mocker: MockerFixture,
            api_mock: RemoteMock,
            log_capturer: LogCapturer,
    ):
        patch_input(["q"], mocker=mocker)

        with log_capturer(loggers=checker.logger):
            await checker._pause(page=1, total=1)
        mocker.stopall()

        assert log_capturer.text.count("Enter one of the following") == 1
        assert "Input not recognised" not in log_capturer.text
        assert "Showing items originally added to" not in log_capturer.text
        assert "Showing tracks for playlist" not in log_capturer.text
        api_mock.assert_not_called()

        assert not checker._skip
        assert checker._quit

    ###########################################################################
    ## ``match_to_input`` step
    ###########################################################################
    # noinspection PyProtectedMember
    @pytest.fixture
    def remaining(self, checker: RemoteItemChecker) -> list[LocalTrack]:
        """
        Set up a random list of items in the ``remaining`` list with missing URIs to be matched via user input.
        Returns a shallow copy list of the items added.
        """
        tracks = random_tracks(20)
        for track in tracks:
            track.uri = None
            assert track.has_uri is None

        checker._remaining.clear()
        checker._remaining.extend(tracks)
        return tracks.copy()

    @staticmethod
    @pytest.mark.slow
    def test_match_to_input_unavailable_all(
            checker: RemoteItemChecker,
            remaining: list[LocalTrack],
            mocker: MockerFixture,
            log_capturer: LogCapturer,
    ):
        # anything after 'ua' will be ignored
        values = ["u", "p", "h", "n", "", "zzzz", "n", "h", "u", "p", "ua", random_str(10, 20), "s", "q"]
        expected = values[-3:]  # stops after 'ua'
        patch_input(values, mocker=mocker)

        with log_capturer(loggers=checker.logger):
            checker._match_to_input(name="test")
        mocker.stopall()

        assert values == expected

        assert log_capturer.text.count("Enter one of the following") == 3
        assert log_capturer.text.count("Input not recognised") == 1

        assert not checker._skip
        assert not checker._quit
        assert not checker._remaining
        assert not checker._switched

        # marked as unavailable
        assert str(remaining[0].path) not in log_capturer.text
        assert remaining[0].uri is None
        assert not remaining[0].has_uri

        # skipped
        assert str(remaining[1].path) in log_capturer.text
        assert remaining[1].uri is None
        assert remaining[1].has_uri is None

        # skipped
        assert str(remaining[2].path) not in log_capturer.text
        assert remaining[2].uri is None
        assert remaining[2].has_uri is None

        # marked as unavailable
        assert str(remaining[3].path) not in log_capturer.text
        assert remaining[3].uri is None
        assert not remaining[3].has_uri

        assert str(remaining[4].path) in log_capturer.text
        for item in remaining[4:]:  # 'ua' triggered, marked as unavailable
            assert item.uri is None
            assert not item.has_uri

    @staticmethod
    @pytest.mark.slow
    def test_match_to_input_skip_all(
            checker: RemoteItemChecker,
            remaining: list[LocalTrack],
            mocker: MockerFixture,
            log_capturer: LogCapturer,
    ):
        # anything after 'na...' will be ignored
        uri_list = random_uris(kind=RemoteObjectType.TRACK, start=5, stop=5)
        # noinspection SpellCheckingInspection
        patch_input(["p", "p", "p", *uri_list, "naaaaaaa", "r"], mocker=mocker)

        with log_capturer(loggers=checker.logger):
            checker._match_to_input(name="test")
        mocker.stopall()

        assert log_capturer.text.count("Enter one of the following") == 1
        assert not checker._skip
        assert not checker._quit
        assert not checker._remaining
        assert checker._switched == remaining[:len(uri_list)]

        # results of each command on the remaining items
        assert log_capturer.text.count(str(remaining[0].path)) == 3
        for uri, item in zip(uri_list, remaining[:len(uri_list)]):  # uri_list
            assert item.uri == uri
            assert item.has_uri

        for item in remaining[len(uri_list):]:  # 'na' triggered, skipped
            assert item.uri is None
            assert item.has_uri is None

    @staticmethod
    def test_match_to_input_return(
            checker: RemoteItemChecker,
            remaining: list[LocalTrack],
            mocker: MockerFixture,
            log_capturer: LogCapturer,
    ):
        # anything after 'r' will be ignored
        patch_input(["u", "u", "u", "r", "q"], mocker=mocker)

        with log_capturer(loggers=checker.logger):
            checker._match_to_input(name="test")
        mocker.stopall()

        assert log_capturer.text.count("Enter one of the following") == 1
        assert not checker._skip
        assert not checker._quit
        assert checker._remaining == remaining[3:]  # returned early before checking all remaining
        assert not checker._switched

        for item in remaining[:3]:  # marked as unavailable
            assert item.uri is None
            assert not item.has_uri

    @staticmethod
    def test_match_to_input_skip(
            checker: RemoteItemChecker,
            remaining: list[LocalTrack],
            mocker: MockerFixture,
            log_capturer: LogCapturer,
    ):
        # anything after 's' will be ignored
        patch_input(["s", "q"], mocker=mocker)

        with log_capturer(loggers=checker.logger):
            checker._match_to_input(name="test")
        mocker.stopall()

        assert log_capturer.text.count("Enter one of the following") == 1
        assert checker._skip
        assert not checker._quit
        assert not checker._remaining
        assert not checker._switched

        for item in remaining:  # skipped
            assert item.uri is None
            assert item.has_uri is None

    @staticmethod
    def test_match_to_input_quit(
            checker: RemoteItemChecker,
            remaining: list[LocalTrack],
            mocker: MockerFixture,
            log_capturer: LogCapturer,
    ):
        # anything after 'q' will be ignored
        patch_input(["q", "s"], mocker=mocker)

        with log_capturer(loggers=checker.logger):
            checker._match_to_input(name="test")
        mocker.stopall()

        assert log_capturer.text.count("Enter one of the following") == 1
        assert not checker._skip
        assert checker._quit
        assert not checker._remaining
        assert not checker._switched

        for item in remaining:  # skipped
            assert item.uri is None
            assert item.has_uri is None

    ###########################################################################
    ## ``match_to_remote`` step
    ###########################################################################
    @staticmethod
    async def test_match_to_remote_no_changes(
            checker: RemoteItemChecker,
            setup_playlist_collection: tuple[RemotePlaylist, BasicCollection],
            setup_empty_playlist_originals: None,
            api_mock: RemoteMock
    ):
        pl, collection = setup_playlist_collection

        # test collection == remote playlist; nothing happens
        await checker._match_to_remote(collection.name)
        assert not checker._switched
        assert not checker._remaining

        pl_pages = api_mock.calculate_pages_from_response(pl.response)
        assert len(await api_mock.get_requests(method="GET", url=re.compile(str(pl.url)))) == pl_pages

    @staticmethod
    async def test_match_to_remote_removed(
            checker: RemoteItemChecker,
            setup_playlist_collection: tuple[RemotePlaylist, BasicCollection],
            setup_empty_playlist_originals: None,
    ):
        pl, collection = setup_playlist_collection

        # extend collection i.e. simulate tracks removed from playlist
        extra_tracks = [track for track in random_tracks(10) if track.has_uri]
        collection.extend(extra_tracks)

        await checker._match_to_remote(collection.name)
        assert not checker._switched
        assert checker._remaining == extra_tracks

    @staticmethod
    async def test_match_to_remote_added(
            checker: RemoteItemChecker,
            setup_playlist_collection: tuple[RemotePlaylist, BasicCollection],
            setup_empty_playlist_originals: None,
    ):
        pl, collection = setup_playlist_collection

        # remove from collection i.e. simulate unmatchable tracks added to playlist
        # tracks are unrelated to remote playlist tracks so this should return no matches
        for item in collection[:5]:
            collection.remove(item)

        await checker._match_to_remote(collection.name)

        assert not checker._switched
        assert not checker._remaining

    @staticmethod
    async def test_match_to_remote_switched(
            checker: RemoteItemChecker,
            setup_playlist_collection: tuple[RemotePlaylist, BasicCollection],
            setup_empty_playlist_originals: None,
            tmp_path: Path
    ):
        pl, collection = setup_playlist_collection

        # switch URIs for some collection items i.e. simulate tracks on remote playlist have been switched
        for i, item in enumerate(collection[:5]):
            collection.items[i] = random_track() | item
            collection[i].uri = random_uri(kind=RemoteObjectType.TRACK)

        await checker._match_to_remote(collection.name)

        assert checker._switched == collection[:5]
        assert not checker._remaining

    @staticmethod
    @pytest.mark.slow
    async def test_match_to_remote_complex(
            checker: RemoteItemChecker,
            setup_playlist_collection: tuple[RemotePlaylist, BasicCollection],
            setup_empty_playlist_originals: None,
    ):
        pl, collection = setup_playlist_collection

        # extend collection i.e. simulate tracks removed from playlist
        extra_tracks = [track for track in random_tracks(10) if track.has_uri]
        collection.extend(extra_tracks)
        collection.extend(extra_tracks)  # add twice, test duplicates processed as expected

        # switch URIs for some collection items i.e. simulate tracks on remote playlist have been switched
        for i, item in enumerate(collection[:5]):
            collection.items[i] = random_track() | item
            collection[i].uri = random_uri(kind=RemoteObjectType.TRACK)

        # remove from collection i.e. simulate unmatchable tracks added to playlist
        for item in collection[5:8]:
            collection.remove(item)

        await checker._match_to_remote(collection.name)
        assert checker._switched == collection[:5]
        assert checker._remaining == 2 * extra_tracks

    @staticmethod
    @pytest.mark.skip(reason="Needs repair. Updates to equality on Track have broken this test.")
    async def test_match_to_remote_complex_with_non_empty_original(
            checker: RemoteItemChecker,
            setup_playlist_collection: tuple[RemotePlaylist, BasicCollection],
    ):
        pl, collection = setup_playlist_collection

        # setup pl and collection such that there is an overlap of a few items between them
        pl_response = pl.copy()
        pl.clear()
        pl.extend(pl_response[:len(pl_response) // 3 + 3])
        assert len(checker._playlist_originals[collection.name]) == len(pl) < len(pl_response)

        coll_items = collection.copy()
        collection.clear()
        collection.extend(coll_items[len(coll_items) // 3 - 3:])

        # switch URIs for some collection items i.e. simulate tracks on remote playlist have been switched
        items_switched = dict([(i, item) for i, item in enumerate(collection) if item not in pl][:3])
        assert items_switched
        for i, item in items_switched.items():
            collection.items[i] = random_track() | item
            collection[i].artist = random_str()
            collection[i].uri = random_uri(kind=RemoteObjectType.TRACK)

        # remove from collection i.e. simulate unmatchable tracks added to playlist
        items_missing = dict([
            (i, item) for i, item in enumerate(collection) if i not in items_switched and item not in pl
        ][:2])
        assert items_missing
        for i, item in items_missing.items():
            collection.items[i] = random_track() | item
            collection[i].artist = random_str()
            collection[i].uri = None

        # these are the items that will show as removed
        extra_tracks = [track for track in random_tracks(6) if track.has_uri]
        collection.extend(extra_tracks)

        expected_removed = [
            item for i, item in enumerate(collection) if item not in pl_response and i not in items_switched
        ]
        assert expected_removed

        await checker._match_to_remote(collection.name)

        assert sorted(checker._switched) == sorted(items_switched.values())
        assert sorted(checker._remaining) == sorted(expected_removed + list(items_missing.values()))

    ###########################################################################
    ## ``check_uri`` meta-step
    ###########################################################################
    @staticmethod
    @pytest.mark.slow
    async def test_check_uri(
            checker: RemoteItemChecker,
            setup_playlist_collection: tuple[RemotePlaylist, BasicCollection],
            setup_empty_playlist_originals: None,
            remaining: list[LocalTrack],
            mocker: MockerFixture,
            log_capturer: LogCapturer,
            api_mock: RemoteMock,
    ):
        pl, collection = setup_playlist_collection

        # extend collection i.e. simulate tracks removed from playlist
        collection.extend(remaining)
        checker._remaining.clear()

        # switch URIs for some collection items i.e. simulate tracks on remote playlist have been switched
        for i, item in enumerate(collection[:5]):
            collection.items[i] = random_track() | item
            collection[i].uri = random_uri(kind=RemoteObjectType.TRACK)

        uri_list = random_uris(kind=RemoteObjectType.TRACK, start=8, stop=8)
        patch_input([*uri_list, "r", "u", "u", "u", "n", "n", "n", "n", "s"], mocker=mocker)  # end on skip
        checker._skip = False
        checker._playlist_check_collections["do not run"] = collection

        with log_capturer(loggers=checker.logger):
            await checker._check_uri()
        mocker.stopall()

        assert not checker._quit
        assert not checker._skip  # skip triggered by input, but should still hold initial value
        assert not checker._switched
        assert not checker._remaining

        assert "do not run" not in log_capturer.text  # skip triggered, 2nd collection should not be processed

        for uri, item in zip(uri_list, remaining[:len(uri_list)]):  # uri_list
            assert item.uri == uri
            assert item.has_uri
        for item in remaining[len(uri_list):]:  # marked as unavailable
            assert item.uri is None
            assert not item.has_uri

        # called 2x: 1 initial, 1 after user inputs 'r'
        pl_pages = api_mock.calculate_pages_from_response(pl.response)
        assert len(await api_mock.get_requests(method="GET", url=re.compile(str(pl.url)))) == 2 * pl_pages

        assert checker._final_switched == collection[:5] + remaining[:len(uri_list)]
        assert checker._final_unavailable == remaining[len(uri_list):len(uri_list) + 3]
        assert checker._final_skipped == remaining[len(uri_list) + 3:]

    ###########################################################################
    ## Main ``check`` function
    ###########################################################################
    @staticmethod
    @pytest.mark.slow
    async def test_check(
            checker: RemoteItemChecker,
            collections: list[BasicCollection],
            playlists: list[RemotePlaylist],
            setup_empty_playlist_originals: None,
            mocker: MockerFixture,
            api_mock: RemoteMock,
    ):
        count = 0

        async def add_collection(self, collection: BasicCollection):
            """Just simply add the collection and associated URL to the ItemChecker without calling API"""
            nonlocal count
            count += 1

            if collection.name not in playlist_originals:
                pl = checker.factory.playlist(await checker.api.create_playlist(collection.name))
                playlist_originals[collection.name] = pl

            self._playlist_originals[collection.name] = playlist_originals[collection.name]
            self._playlist_check_collections[collection.name] = collection

        playlist_originals = {pl.name: pl for pl in playlists}
        mocker.patch.object(RemoteItemChecker, "_create_playlist", new=add_collection)

        interval = len(collections) // 3
        checker.interval = interval
        batched_collections = batched(collections, interval)

        # mark all items in 1st and 2nd batch as unavailable, skip after the 2nd batch and quit
        batch_1 = next(batched_collections)
        batch_2 = next(batched_collections)
        values = ["", *["ua" for _ in batch_1], "s", *["ua" for _ in batch_2]]
        patch_input(values, mocker=mocker)

        result = await checker(collections)
        mocker.stopall()

        assert count == len(batch_1) + len(batch_2)  # only 2 batches executed

        # resets after each run
        assert not checker._remaining
        assert not checker._switched
        assert not checker._final_switched
        assert not checker._final_unavailable
        assert not checker._final_skipped

        assert not result.switched
        assert len(result.unavailable) == sum(map(len, batch_1 + batch_2))
        assert not result.skipped

        # all items in all collections in the 1st and 2nd batches were marked as unavailable
        for coll in batch_1 + batch_2:
            for item in coll:
                assert item.uri is None
                assert not item.has_uri

        # deleted only the playlists in the first 2 batches
        requests = []
        for playlist in (playlist_originals[collection.name] for collection in batch_1 + batch_2):
            requests += await api_mock.get_requests(method="DELETE", url=re.compile(str(playlist.url)))

        assert len(requests) == len(batch_1) + len(batch_2)
