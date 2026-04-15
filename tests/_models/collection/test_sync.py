from unittest.mock import patch

import pytest
from faker import Faker
from mytunes import MODULE_ROOT
# noinspection PyProtectedMember
from mytunes._models.collection._sync import get_sync_items, get_sync_items_for_add, get_sync_items_for_refresh, \
    get_sync_items_for_sync
from mytunes.exception import RequestError
from mytunes._models.item.track import RemoteTrack
from tests.remote import SimpleURI


def test_get_sync_items_calls_expected_getter():
    with (
        patch(f"{MODULE_ROOT}._models.collection._sync.get_sync_items_for_add") as mock_add,
        patch(f"{MODULE_ROOT}._models.collection._sync.get_sync_items_for_refresh") as mock_refresh,
        patch(f"{MODULE_ROOT}._models.collection._sync.get_sync_items_for_sync") as mock_sync,
    ):
        get_sync_items(kind="new", initial=(), remote=())
        mock_add.assert_called_once()
        mock_refresh.assert_not_called()
        mock_sync.assert_not_called()

        get_sync_items(kind="refresh", initial=(), remote=())
        mock_add.assert_called_once()
        mock_refresh.assert_called()
        mock_sync.assert_not_called()

        get_sync_items(kind="sync", initial=(), remote=())
        mock_add.assert_called()
        mock_refresh.assert_called()
        mock_sync.assert_called()


def test_get_sync_items_fails_on_unknown_type():
    with pytest.raises(RequestError, match="Invalid sync type"):
        # noinspection PyTypeChecker
        get_sync_items(kind="unknown_type", initial=(), remote=())


def test_get_sync_items_for_add(faker: Faker):
    initial = [SimpleURI.from_id(i, kind=RemoteTrack.type) for i in range(faker.random_int(10, 15))]
    remote = [SimpleURI.from_id(i, kind=RemoteTrack.type) for i in range(faker.random_int(1, 10))]

    add, remove, unchanged = get_sync_items_for_add(initial, remote)
    assert add == initial[len(remote):]
    assert remove == []
    assert unchanged == remote


def test_get_sync_items_for_refresh(faker: Faker):
    initial = [SimpleURI.from_id(i, kind=RemoteTrack.type) for i in range(faker.random_int(10, 15))]
    remote = [SimpleURI.from_id(i, kind=RemoteTrack.type) for i in range(faker.random_int(1, 10))]

    add, remove, unchanged = get_sync_items_for_refresh(initial, remote)
    assert add == initial
    assert remove == remote
    assert unchanged == []


def test_get_sync_items_for_sync(faker: Faker):
    initial = [SimpleURI.from_id(i, kind=RemoteTrack.type) for i in range(faker.random_int(5, 15))]
    remote = [SimpleURI.from_id(i, kind=RemoteTrack.type) for i in range(faker.random_int(1, 10))]
    remote += [
        SimpleURI.from_id(i + len(initial) + len(remote), kind=RemoteTrack.type)
        for i in range(faker.random_int(1, 10))
    ]

    add, remove, unchanged = get_sync_items_for_sync(initial, remote)
    assert add == sorted(set(initial) - set(remote), key=lambda uri: int(uri.id))
    assert remove == sorted(set(remote) - set(initial), key=lambda uri: int(uri.id))
    assert unchanged == sorted(set(initial) & set(remote), key=lambda uri: int(uri.id))
