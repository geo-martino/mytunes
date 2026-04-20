from collections.abc import Collection

from mytunes.core._collection import SyncRemoteResult
from mytunes.properties.uri import URI


def assert_sync_items_result(
        result: SyncRemoteResult,
        initial: Collection[URI],
        added: Collection[URI],
        removed: Collection[URI],
        unchanged: Collection[URI],
):
    assert result.start == len(initial)
    assert result.added == len(added)
    assert result.removed == len(removed)
    assert result.unchanged == len(unchanged)
    assert result.difference == len(added) - len(removed)
    assert result.final == len(initial) + len(added) - len(removed)
