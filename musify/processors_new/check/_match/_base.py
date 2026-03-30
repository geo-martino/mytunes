from abc import abstractmethod
from collections.abc import Collection, Iterable
from typing import Any

from pydantic import Field

from musify.models import ResourceModel
from musify.models.properties.logger import HasLogger
from musify.models.properties.uri import HasURI, HasMutableURI, URI
from musify.processors_new import Processor
from musify.processors_new.check._page import CheckerPage
from musify.processors_new.check.result import CheckResult
from musify.processors_new.match import Matcher


# noinspection PyAbstractClass
class CheckerMatch(Processor, HasLogger):
    page: CheckerPage = Field(
        description="The state of the current page"
    )
    matcher: Matcher = Field(
        description=(
            "The matcher to use for confirming closest matches returned by the API "
            "when comparing changes in playlists."
        ),
    )

    @abstractmethod
    async def match[CT: HasURI](self, items: Collection[CT], uri: URI, name: str) -> CheckResult[CT]:
        """Match the items and return the results."""
        raise NotImplementedError

    ###########################################################################
    ## Match/Compare
    ###########################################################################
    def _match_item_with_others[T: HasURI](self, item: T, others: Collection[T], method: str) -> T | None:
        if not isinstance(item, HasMutableURI):
            return

        match = self.matcher.match(item, others)
        if match is None or not match.has_uri:
            return

        messages = [f"Updating {item.type} URI", f"{item.uri} -> {match.uri}"]
        self._log_debug(method, item, messages, pad="<")
        item.uri = match.uri

        return match

    ###########################################################################
    ## State getters
    ###########################################################################
    @staticmethod
    def get_valid_items[CT: HasURI](items: Iterable[CT]) -> list[CT]:
        """Get all items with valid URIs"""
        return [item for item in items if isinstance(item, HasURI) and item.has_uri]

    @staticmethod
    def get_missing_items[CT: HasURI](items: Iterable[CT]) -> list[CT]:
        """Get all items with missing URIs"""
        return [item for item in items if isinstance(item, HasURI) and item.has_uri is None]

    @staticmethod
    def get_unavailable_items[CT: HasURI](items: Iterable[CT]) -> list[CT]:
        """Get all items which are confirmed to be unavailable or cannot have a URI set for other reasons."""
        return [item for item in items if isinstance(item, HasURI) and item.has_uri is False]

    @staticmethod
    def get_invalid_items[CT: ResourceModel](items: Iterable[CT]) -> list[CT]:
        """Get all items cannot have a URI set."""
        return [item for item in items if not isinstance(item, HasMutableURI)]

    ###########################################################################
    ## Logging
    ###########################################################################
    def _log_debug(self, method: str, item: Any, messages: str | Iterable, count: int | None = None, pad: str = " ") -> None:
        if count is not None and isinstance(messages, str):
            messages = f"{count:>6} {messages}"

        log = self._format_item_message(method=method, item=item, messages=messages, pad=pad)
        self.logger.debug(log)
