from abc import ABCMeta, abstractmethod
from copy import deepcopy
from random import sample
from typing import Iterable, Any

import pytest

from musify.base import MusifyItem
from musify.exception import MusifyTypeError
from musify.libraries.core.collection import MusifyCollection
from musify.libraries.core.object import Playlist, Track, Library
from tests.libraries.core.collection import MusifyCollectionTester
from tests.testers import MusifyItemTester


class TrackTester(MusifyItemTester, metaclass=ABCMeta):

    @abstractmethod
    def item_equal_properties(self, *args, **kwargs) -> MusifyItem:
        """
        Yields an :py:class:`MusifyItem` object that equals the ``item`` being tested based on properties
        """
        raise NotImplementedError

    @abstractmethod
    def item_unequal_properties(self, *args, **kwargs) -> MusifyItem:
        """
        Yields an :py:class:`MusifyItem` object that is does not equal the ``item`` being tested based on properties
        """
        raise NotImplementedError

    @staticmethod
    def test_equality_on_properties(item: Track, item_equal_properties: Track, item_unequal_properties: Track):
        assert hash(item) == hash(item_equal_properties)
        assert item == item_equal_properties

        assert hash(item) != hash(item_unequal_properties)
        assert item != item_unequal_properties


class PlaylistTester(MusifyCollectionTester, metaclass=ABCMeta):

    @abstractmethod
    def playlist(self, *args, **kwargs) -> Playlist:
        """Yields an :py:class:`Playlist` object to be tested as pytest.fixture."""
        raise NotImplementedError

    @pytest.fixture
    def collection(self, playlist: Playlist) -> MusifyCollection:
        return playlist

    # noinspection PyTypeChecker
    @staticmethod
    def test_merge_input_validation(playlist: Playlist, collection_merge_invalid: Iterable[MusifyItem]):
        with pytest.raises(MusifyTypeError):
            playlist.merge(collection_merge_invalid)

    @staticmethod
    def test_merge[T: Track](playlist: Playlist[T], collection_merge_items: Iterable[T]):
        initial_count = len(playlist)
        items = [item for item in collection_merge_items]

        playlist.merge([items[0]])
        assert len(playlist) == initial_count + 1
        assert playlist[-1] == items[0]

        playlist.merge(playlist.items + items[:-1])
        assert len(playlist) == initial_count + len(items) - 1

        playlist.merge(playlist.items + items)
        assert len(playlist) == initial_count + len(items)

    @staticmethod
    def test_merge_with_reference[T: Track](playlist: Playlist[T], collection_merge_items: Iterable[T]):
        # setup collections so 2 items are always removed and many items are always added
        reference = deepcopy(playlist)
        reference_items = sample(reference.items, k=(len(reference.items) // 2) + 1)
        reference.clear()
        reference.extend(reference_items)
        assert len(reference) >= 3

        other = [item for item in collection_merge_items]
        other.extend(reference[:2])  # both other and playlist have item 0, playlist does not have item 1
        other.extend(reference[3:])  # both other and playlist has items 3+

        playlist_items = [item for item in playlist if item not in reference]
        playlist.clear()
        playlist.extend(playlist_items)
        playlist.append(reference[0])  # both other and playlist have item 0
        playlist.extend(reference[2:])  # playlist has item 2, both other and playlist has items 3+
        playlist.append(next(item for item in other if item not in reference and item not in playlist))

        removed = [item for item in reference if item not in other or item not in playlist]
        assert len(removed) >= 2

        added = [item for item in other if item not in reference]
        added += [item for item in playlist if item not in reference and item not in added]
        assert added

        playlist.merge(other=other, reference=reference)
        assert all(item not in playlist for item in removed)
        assert all(item in playlist for item in added)
        assert len(playlist) == len(reference) - len(removed) + len(added)

    @staticmethod
    def test_merge_dunder_methods[T: Track](playlist: Playlist[T], collection_merge_items: Iterable[T]):
        initial_count = len(playlist)
        other = deepcopy(playlist)
        other.tracks.clear()
        other.tracks.extend(collection_merge_items)

        new_pl = playlist | other
        assert len(new_pl) == initial_count + len(other)
        assert new_pl[initial_count:] == other.items
        assert len(playlist) == initial_count

        playlist |= other
        assert len(playlist) == initial_count + len(other)
        assert playlist[initial_count:] == other.items


class LibraryTester(MusifyCollectionTester, metaclass=ABCMeta):
    """
    Run generic tests for :py:class:`Library` implementations.
    The collection must have 3 or more playlists and all playlists must be unique.
    """

    @abstractmethod
    def library(self, *args, **kwargs) -> Library:
        """Yields a loaded :py:class:`Library` object to be tested as pytest.fixture."""
        raise NotImplementedError

    @pytest.fixture
    def collection(self, library: Library) -> MusifyCollection:
        return library

    @staticmethod
    def assert_merge_playlists(
            library: Library,
            test: Any,
            extend_playlists: Iterable[Playlist] = (),
            new_playlists: Iterable[Playlist] = ()
    ):
        """Run merge playlists function on ``source`` library against ``test_values`` and assert expected results"""
        # fine-grained merge functionality is tested in the playlist tester
        # we just need to assert the playlist was modified in some way
        original_playlists = deepcopy(library.playlists)
        library.merge_playlists(test)

        test_names = {pl.name for pl in extend_playlists} | {pl.name for pl in new_playlists}
        for pl in library.playlists.values():  # test unchanged playlists are unchanged
            if pl.name in test_names:
                continue
            assert library.playlists[pl.name].tracks == pl.tracks

        for pl in extend_playlists:
            assert library.playlists[pl.name].tracks != original_playlists[pl.name].tracks
            assert library.playlists[pl.name].tracks == pl.tracks

        for pl in new_playlists:
            assert pl.name not in original_playlists
            assert library.playlists[pl.name].tracks == pl.tracks
            assert id(library.playlists[pl.name]) != id(pl)  # deepcopy occurred

    @pytest.fixture
    def merge_playlists(self, library: Library) -> list[Playlist]:
        """Set of playlists to be used in ``merge_playlists`` tests."""
        # playlist order: extend, create, unchanged
        return deepcopy(sample(list(library.playlists.values()), k=3))

    @pytest.fixture
    def merge_playlists_extend(
            self, library: Library, merge_playlists: list[Playlist], collection_merge_items: Iterable[MusifyItem]
    ) -> list[Playlist]:
        """Set of playlists that already exist in the ``library`` with extra tracks to be merged"""
        merge_playlist = merge_playlists[0]
        merge_playlist.extend(collection_merge_items)
        assert merge_playlist.tracks != library.playlists[merge_playlist.name].tracks

        return [merge_playlist]

    @pytest.fixture
    def merge_playlists_new(self, library: Library, merge_playlists: list[Playlist]) -> list[Playlist]:
        """Set of new playlists to merge with the given ``library``"""
        new_playlist = merge_playlists[1]
        library.playlists.pop(new_playlist.name)
        assert new_playlist.name not in library.playlists

        return [new_playlist]

    def test_merge_playlists_as_collection(
            self,
            library: Library,
            merge_playlists: list[Playlist],
            merge_playlists_extend: list[Playlist],
            merge_playlists_new: list[Playlist],
    ):
        self.assert_merge_playlists(
            library=library,
            test=merge_playlists,  # Collection[Playlist]
            extend_playlists=merge_playlists_extend,
            new_playlists=merge_playlists_new
        )

    def test_merge_playlists_as_mapping(
            self,
            library: Library,
            merge_playlists: list[Playlist],
            merge_playlists_extend: list[Playlist],
            merge_playlists_new: list[Playlist],
    ):
        self.assert_merge_playlists(
            library=library,
            test={pl.name: pl for pl in merge_playlists},  # Mapping[str, Playlist]
            extend_playlists=merge_playlists_extend,
            new_playlists=merge_playlists_new
        )

    def test_merge_playlists_as_library(
            self,
            library: Library,
            merge_playlists: list[Playlist],
            merge_playlists_extend: list[Playlist],
            merge_playlists_new: list[Playlist],
    ):
        test = deepcopy(library)
        test.playlists.clear()
        test.playlists.update({pl.name: pl for pl in merge_playlists})

        self.assert_merge_playlists(
            library=library, test=test, extend_playlists=merge_playlists_extend, new_playlists=merge_playlists_new
        )
