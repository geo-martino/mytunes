import itertools
from collections.abc import Collection, Sequence
from functools import partial
from webbrowser import open as webopen

from pydantic import Field
from rich.progress import TaskID
from termcolor import colored
from yarl import URL

from ..._models import AttributeModel, ResourceModel
from ..._models.properties.order import Position
from musify._types import HttpURL
from .._base.inputs import PageProcessor


class StorePausePage[IT: AttributeModel](PageProcessor):
    items: Sequence[IT] = Field(
        description="The items to be processed by this page"
    )
    urls: Sequence[Sequence[HttpURL]] = Field(
        description="The URLs to be processed by this page for each item."
    )

    @property
    def fields(self) -> tuple[str, ...]:
        """The valid fields for the items in this page"""
        classes: set[type[AttributeModel]] = {type(it) for it in self.items}
        available_fields = set(
            itertools.chain.from_iterable(kls.__tag_attributes__ for kls in classes)
        )
        valid_fields = {
            field for field in available_fields if any(getattr(item, field) is not None for item in self.items)
        }

        return tuple(valid_fields)

    @property
    def types(self) -> str:
        return self.logger.format_types_to_string(self.items) or "items"

    def open_sites(self) -> None:
        """Open the sites for this page."""
        self.logger.debug(f"Opening sites for {len(self.items)} {self.types}")
        tasks = [
            partial(self._open_sites_for_item, item=item, urls=urls)
            for item, urls in zip(self.items, self.urls, strict=True)
        ]
        remove = self.position.number == self.position.total
        self.logger.run_tasks(tasks, task_id=self.task_id, remove=remove)

    def _open_sites_for_item(self, item: IT, urls: Collection[URL]) -> None:
        self.logger.debug(f"Opening {len(urls)} URLs for {self._get_item_log_value(item)!r}")
        for url in urls:
            webopen(str(url))

    ###########################################################################
    ## Pause page
    ###########################################################################
    @property
    def _header(self) -> str:
        header = f"Opened {sum(len(urls) for urls in self.urls)} sites for {len(self.items)} {self.types}. "
        header += f"You may now search for and download the {self.types}."
        return colored(header, "blue", attrs=["bold"])

    @property
    def _options(self) -> dict[str, str]:
        return {
            "<Return/Enter>": "Once you are finished with this batch, continue on to the next batch",
            "r": f"Re-open all sites for the current batch of {self.types}",
            "<Fields>":
                f"Re-open all sites for the current batch of {self.types} using the input list of fields, "
                "each separated by a space e.g. title artist album",
            "q": f"Skip opening sites for any remaining {self.types} and quit",
        }

    def pause(self) -> tuple[str, ...] | None:
        super().pause()

        while option := self._get_user_input():
            match option.casefold():
                case "r":  # return True to re-open all sites
                    self.open_sites()

                case opt if fields := self._get_filtered_fields_from_input(opt):
                    # return the valid fields to re-open all sites for these fields
                    return fields

                case _:
                    self._log_unrecognised_input(option)

    def _get_filtered_fields_from_input(self, inp: str) -> tuple[str, ...]:
        input_fields = set(inp.split())
        filtered_fields = input_fields & set(self.fields)

        if filtered_fields and filtered_fields != input_fields:
            self.logger.warning(
                f"Some fields were not recognised: {", ".join(input_fields - filtered_fields)}. "
                f"Using only recognised fields: {", ".join(filtered_fields)}."
            )

        return tuple(filtered_fields)
