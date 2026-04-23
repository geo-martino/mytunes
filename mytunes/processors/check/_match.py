import sys
from abc import abstractmethod
from collections.abc import Iterable, Sequence, Collection
from contextlib import suppress
from typing import Any, ClassVar

from pydantic import Field, InstanceOf, OnErrorOmit, validate_call, ValidationError
from termcolor import colored

from mytunes.core.api import RemoteAPI
from mytunes.core.properties.logger import HasLogger
from mytunes.core.properties.name import HasName
from mytunes.core.properties.uri import HasURI, HasMutableURI, URI
from mytunes.processors import OptionsProcessor
from mytunes.processors import Processor
from mytunes.processors._flow import SkipPage
from mytunes.processors.check._page import CheckerPage
from mytunes.processors.check.result import CheckResult
from mytunes.result import LogFormatter


# noinspection PyAbstractClass
class BaseMatch[API: RemoteAPI, IT: HasMutableURI](Processor, HasLogger):
    _method: ClassVar[str] = "MATCH"

    # WORKAROUND: use `InstanceOf` here to prevent revalidation
    #  which creates a new page hence not preserving current page state
    #  Could alternatively drop the generics, not sure what is best...
    page: InstanceOf[CheckerPage[API, IT]] = Field(
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
    async def match[CT: HasURI](self, items: Sequence[IT]) -> CheckResult[CT]:
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


# noinspection PyAbstractClass
class BaseInputMatch[API: RemoteAPI, IT: HasMutableURI](BaseMatch[API, IT], OptionsProcessor):
    async def match(self, items: Sequence[IT]) -> CheckResult[IT]:
        """Match the given items that have missing URIs with user input."""
        missing = self.get_missing_items(items)
        if not missing:
            message = "No items with mutable URIs to match to input, skipping match"
            self._log_skip(message)
            return CheckResult(name=self.name)

        self._log_debug(f"Getting user input for {len(missing)} items")
        self._print_help_text(header=self._get_header(len(missing)))

        initial = [it.model_copy() for it in missing]
        formatter = self._configure_formatter_for_items(missing)
        option = None

        with suppress(SkipPage):  # suppress so we can still compare changes and return a result
            for item in missing:
                option = await self._match_item_with_input(item, others=items, option=option, formatter=formatter)

        return self._compare_uri_changes(initial=initial, changes=missing)

    @classmethod
    def _configure_formatter_for_items(cls, items: Iterable) -> LogFormatter:
        width = min(
            max(len(item.name) if isinstance(item, HasName) else 0 for item in items),
            cls.input_formatter.max_width or sys.maxsize,
        )
        kwargs = vars(cls.input_formatter)
        kwargs.pop("width", None)

        return cls.input_formatter.__class__(**kwargs, width=width or None)

    def _compare_uri_changes(self, initial: Iterable[IT], changes: Iterable[IT]) -> CheckResult[IT]:
        changed = []
        unchanged = []
        unavailable = []
        skipped = []

        for init, change in zip(initial, changes, strict=True):
            if init.has_uri is not False and change.has_uri is False:
                unavailable.append(change)
            elif init.has_uri is None and change.has_uri is None:
                skipped.append(change)
            elif init.uri == change.uri:
                unchanged.append(change)
            else:
                changed.append(change)

        return CheckResult(
            name=self.name, changed=changed, unchanged=unchanged, unavailable=unavailable, skipped=skipped
        )

    ###########################################################################
    ## Pause page
    ###########################################################################
    @abstractmethod
    async def _match_item_with_input(
            self, item: IT, others: Collection[IT], option: str | None, formatter: LogFormatter
    ) -> str | None:
        raise NotImplementedError

    def _get_header(self, count: int) -> str:
        message = self._header.format(count=count)
        name = colored(self.name, "blue", attrs=["bold"])
        return f"{name}: {message}"

    def _set_uri(self, item: IT, value: str | None) -> bool:
        with suppress(ValidationError):
            uri = self.page.api.create_uri(value=value, kind=item.type)
            if uri.type != item.type:
                self._log_debug(f"Invalid URI type: {item.type}", item=item)
                return False

            self._log_debug(f"Setting {item.type} URI: {str(uri)}", item=item, pad="<")
            item.uri = uri
            return True
        return False

    def _set_unavailable_uri(self, item: IT) -> bool:
        return self._set_uri(item, value=None)

    def _drop_uri(self, item: IT) -> bool:
        self._log_debug(f"Marking {item.type} as missing", item=item, pad="<")
        del item.uri
        return True
