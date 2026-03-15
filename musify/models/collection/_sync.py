from typing import Literal, Collection

from musify.exception import MusifyValueError

SYNC_TYPE = Literal["new", "refresh", "sync"]


def get_sync_message(kind: SYNC_TYPE, item_type: str, from_type: str) -> str:
    """Format a message describing the sync operation being performed for the given type and item type."""
    match kind:
        case "new":
            return f"adding new {item_type} only"
        case "refresh":
            return f"clearing all {item_type} from {from_type} first"
        case "sync":
            return f"clearing extra {item_type} from {from_type} first"
        case _:
            raise MusifyValueError(f"Invalid sync type: {kind}")


def get_sync_items[T](
        kind: SYNC_TYPE, initial: Collection[T], remote: Collection[T]
) -> tuple[list[T], list[T], list[T]]:
    """Get the items to add, remove and keep unchanged for a sync of the given type."""
    match kind:
        case "new":
            return get_sync_items_for_add(initial, remote)
        case "refresh":
            return get_sync_items_for_refresh(initial, remote)
        case "sync":
            return get_sync_items_for_sync(initial, remote)
        case _:
            raise MusifyValueError(f"Invalid sync type: {kind}")


def get_sync_items_for_add[T](initial: Collection[T], remote: Collection[T]) -> tuple[list[T], list[T], list[T]]:
    """Get the items to add, remove and keep unchanged for a "new" type sync."""
    add = [uri for uri in initial if uri not in remote]
    remove = []
    unchanged = list(remote)
    return add, remove, unchanged


def get_sync_items_for_refresh[T](initial: Collection[T], remote: Collection[T]) -> tuple[list[T], list[T], list[T]]:
    """Get the items to add, remove and keep unchanged for a "refresh" type sync."""
    add = list(initial)
    remove = list(remote)
    unchanged = []
    return add, remove, unchanged


def get_sync_items_for_sync[T](initial: Collection[T], remote: Collection[T]) -> tuple[list[T], list[T], list[T]]:
    """Get the items to add, remove and keep unchanged for a "sync" type sync."""
    add = [uri for uri in initial if uri not in remote]
    remove = [uri for uri in remote if uri not in initial]
    unchanged = [uri for uri in remote if uri in initial]
    return add, remove, unchanged
