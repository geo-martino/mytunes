from collections.abc import Collection
from typing import Literal, Annotated

from pydantic import NonNegativeInt, Field
from pydantic.json_schema import JsonSchemaValue

from mytunes._models.exception import RequestError
from mytunes._models.result import LogFormatter, CountResult, MapLogFormatter


class SyncRemoteResult(CountResult):
    """Stores the results of a sync with a remote service."""
    start: Annotated[
        NonNegativeInt,
        LogFormatter(width=6, alignment="right", colour="blue", colour_attributes=["bold"]),
    ] = Field(
        description="The total number of items in the resource before the sync."
    )
    added: Annotated[
        NonNegativeInt,
        LogFormatter(
            width=6, alignment="right", colour="blue", colour_attributes=["bold"], condition=lambda x: x == 0
        ),
        LogFormatter(
            width=6, alignment="right", colour="green", colour_attributes=["bold"], condition=lambda x: x > 0
        ),
    ] = Field(
        description="The number of items added to the resource."
    )
    removed: Annotated[
        NonNegativeInt,
        LogFormatter(
            width=6, alignment="right", colour="blue", colour_attributes=["bold"], condition=lambda x: x == 0
        ),
        LogFormatter(
            width=6, alignment="right", colour="red", colour_attributes=["bold"], condition=lambda x: x > 0
        ),
    ] = Field(
        description="The number of items removed from the resource."
    )
    unchanged: Annotated[
        NonNegativeInt,
        LogFormatter(
            width=6, alignment="right", colour="blue", colour_attributes=["bold"], condition=lambda x: x == 0
        ),
        LogFormatter(
            width=6, alignment="right", colour="yellow", colour_attributes=["bold"], condition=lambda x: x > 0
        ),
    ] = Field(
        description="The number of items that were in the remote resource both before and after the sync."
    )
    difference: Annotated[
        int,
        LogFormatter(
            width=6, alignment="right", colour="blue", colour_attributes=["bold"], condition=lambda x: x == 0
        ),
        LogFormatter(
            width=6, alignment="right", colour="magenta", colour_attributes=["bold"], condition=lambda x: x != 0
        ),
    ] = Field(
        description="The difference between the total number items from before and after the sync."
    )
    final: Annotated[
        NonNegativeInt,
        LogFormatter(width=6, alignment="right", colour="blue", colour_attributes=["bold"]),
    ] = Field(
        description="The total number of items in the resource after the sync."
    )
    properties: Annotated[
        JsonSchemaValue,
        MapLogFormatter(
            value=lambda x: ", ".join(x.keys()),
            colour="blue",
            condition=lambda x: len(x) > 0,
            include_name_in_log=False
        ),
    ] = Field(
        description="The modified properties of the sync operation, if any.",
        default_factory=dict,
    )


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
            raise RequestError(f"Invalid sync type: {kind}")


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
            raise RequestError(f"Invalid sync type: {kind}")


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
