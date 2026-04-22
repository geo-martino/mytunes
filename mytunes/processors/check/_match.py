from abc import abstractmethod
from collections.abc import Iterable, Sequence, Collection
from typing import Any, ClassVar

from pydantic import Field, InstanceOf, OnErrorOmit, validate_call

from mytunes.core.properties.logger import HasLogger
from mytunes.core.properties.uri import HasURI, HasMutableURI
from mytunes.processors.check._page import CollectionsPage
from mytunes.processors.check.result import CheckResult
from .._base import Processor
from mytunes.core.api import RemoteAPI


# noinspection PyAbstractClass
class CheckerMatch[API: RemoteAPI, IT: HasMutableURI](Processor, HasLogger):
    _method: ClassVar[str] = "MATCH"

    # WORKAROUND: use `InstanceOf` here to prevent revalidation
    #  which creates a new page hence not preserving current page state
    #  Could alternatively drop the generics, not sure what is best...
    page: InstanceOf[CollectionsPage[API, IT]] = Field(
        description="The state of the current page"
    )

    @property
    @abstractmethod
    def name(self) -> str:
        """The name of the related collection."""
        raise NotImplementedError

    ###########################################################################
    ## Match/Compare
    ###########################################################################
    @abstractmethod
    async def match[CT: HasURI](self, items: Collection[IT]) -> CheckResult[CT]:
        """Match the items and return the results."""
        raise NotImplementedError

    @staticmethod
    @validate_call
    def get_valid_items(items: Sequence[OnErrorOmit[IT]]) -> list[IT]:
        """Get all items with valid URIs"""
        return [item for item in items if item.has_uri]

    @staticmethod
    @validate_call
    def get_missing_items(items: Sequence[OnErrorOmit[IT]]) -> list[IT]:
        """Get all items with missing URIs"""
        return [item for item in items if item.has_uri is None]

    @staticmethod
    @validate_call
    def get_unavailable_items(items: Sequence[OnErrorOmit[IT]]) -> list[IT]:
        """Get all items which are confirmed to be unavailable or cannot have a URI set for other reasons."""
        return [item for item in items if item.has_uri is False]

    ###########################################################################
    ## Logging
    ###########################################################################
    def __log_debug(self, messages: str | Iterable, item: Any, count: int, pad: str, method: str) -> None:
        if count is not None and isinstance(messages, str):
            messages = f"{count:>6} {messages}"

        log = self._format_item_message(method=method, item=item or self.name, messages=messages, pad=pad)
        self._logger.debug(log)

    def _log_debug(
            self, messages: str | Iterable, item: Any = None, count: int | None = None, pad: str = " ",
    ) -> None:
        self.__log_debug(messages, item=item, count=count, pad=pad, method=self._method)

    def _log_skip(
            self, messages: str | Iterable, item: Any = None, count: int | None = None, pad: str = " ",
    ) -> None:
        self.__log_debug(messages, item=item, count=count, pad=pad, method="SKIP")
