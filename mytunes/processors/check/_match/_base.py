from abc import abstractmethod
from collections.abc import Collection, Iterable, Sequence
from typing import Any, ClassVar

from pydantic import Field, InstanceOf, OnErrorOmit

from mytunes.processors.check._page import CheckerPage, _ApiT
from mytunes.processors.check.result import CheckResult
from mytunes.processors.match import Matcher
from mytunes.properties.logger import HasLogger
from mytunes.properties.uri import HasURI, HasMutableURI, HasImmutableURI
from ..._base import Processor


# noinspection PyAbstractClass
class CheckerMatch[IT: HasMutableURI](Processor, HasLogger, HasImmutableURI):
    type: ClassVar[str] = "playlist"

    # WORKAROUND: use `InstanceOf` here to prevent revalidation
    #  which creates a new page hence not preserving current page state
    #  Could alternatively drop the generics, not sure what is best...
    page: InstanceOf[CheckerPage[_ApiT, IT]] = Field(
        description="The state of the current page"
    )
    items: Sequence[OnErrorOmit[IT]] = Field(
        description="The items with missing URIs to match."
    )

    matcher: Matcher = Field(
        description=(
            "The matcher to use for confirming closest matches returned by the API "
            "when comparing changes in playlists."
        ),
    )

    @property
    def name(self) -> str:
        """The name of the related playlist."""
        return self.page.get_playlist_name(self.uri)

    @property
    def valid_items(self) -> list[IT]:
        """Get all items with valid URIs"""
        return [item for item in self.items if item.has_uri]

    @property
    def missing_items(self) -> list[IT]:
        """Get all items with missing URIs"""
        return [item for item in self.items if item.has_uri is None]

    @property
    def unavailable_items(self) -> list[IT]:
        """Get all items which are confirmed to be unavailable or cannot have a URI set for other reasons."""
        return [item for item in self.items if item.has_uri is False]

    ###########################################################################
    ## Match/Compare
    ###########################################################################
    @abstractmethod
    async def match[CT: HasURI](self) -> CheckResult[CT]:
        """Match the items and return the results."""
        raise NotImplementedError

    def _match_item_with_others[OT: HasURI](self, item: IT, others: Collection[OT], method: str) -> OT | None:
        if not isinstance(item, HasMutableURI):
            return

        match = self.matcher.match(item, others)
        if match is None or not match.has_uri:
            return

        messages = [f"Updating {item.type} URI", f"{item.uri} -> {match.uri}"]
        self._log_debug(method, messages, item=item, pad="<")
        item.uri = match.uri

        return match

    ###########################################################################
    ## Logging
    ###########################################################################
    def _log_debug(
            self, method: str, messages: str | Iterable, item: Any = None, count: int | None = None, pad: str = " "
    ) -> None:
        if count is not None and isinstance(messages, str):
            messages = f"{count:>6} {messages}"

        log = self._format_item_message(method=method, item=item or self.name, messages=messages, pad=pad)
        self._logger.debug(log)
