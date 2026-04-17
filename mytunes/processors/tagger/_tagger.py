from collections.abc import Sequence, Collection, Iterable
from functools import partial
from typing import Union, Annotated

from mytunes.processors.filters import Filter
from pydantic import AliasChoices, Field

from ._setter import Setter
from .._base import Processor
from ..._models import AttributeModel, ResourceModel
from ..._models.properties.logger import HasLogger, HasProgress
from ..._models.result import Result, MapLogFormatter
from ..._types import TO_TUPLE
from ...logger import Logger, REPORT


class TaggerResult(Result):
    fields: Annotated[
        Sequence[str],
        TO_TUPLE,
        MapLogFormatter(
            value=lambda values: Logger.format_list_to_string(values),
            colour="blue",
            colour_attributes=["bold"],
            include_name_in_log=False,
        ),
    ] = Field(
        description="The fields that were modified.",
        default_factory=tuple
    )


class Tagger[IT: AttributeModel](Processor, HasLogger, HasProgress):
    item_filter: Union[Filter.annotation, None] = Field(
        default=None,
        validation_alias=AliasChoices("on", "filter"),
    )
    setters: Sequence[Setter.annotation] = Field(
        description="The setters to use to apply tag values to items.",
        validation_alias=AliasChoices("fields", "rules"),
    )

    def filter_items(self, items: Iterable[IT]) -> Iterable[IT]:
        """Apply the item filter to the items provided (if applicable)."""
        if self.item_filter is None or not self.item_filter.ready:
            return items
        return filter(self.item_filter.check, items)

    def set_tags_to_items(self, items: Iterable[IT]) -> dict[str, TaggerResult]:
        """Apply setters to the item from the collection."""
        items = list(self.filter_items(items))

        task_id = self._progress.add_task(description="Applying tags to items", total=len(items))
        tasks = (partial(self._set_tags_to_item_with_key, item=item, collection=items) for item in items)
        results = dict(self._run_tasks(tasks, task_id=task_id))

        return results

    def _set_tags_to_item_with_key(self, item: IT, collection: Collection[IT]) -> tuple[str, TaggerResult] | None:
        result = self.set_tags_to_item(item, collection)
        if not result:
            return

        if isinstance(item, ResourceModel):
            key = next(map(str, sorted(item.unique_keys, key=lambda k: isinstance(k, str))), None)
        else:
            key = str(id(item))
        return key, result

    def set_tags_to_item(self, item: IT, collection: Collection[IT]) -> TaggerResult:
        """Apply setters to the item from the collection."""
        fields = []
        for setter in self.setters:
            is_set = setter.set(item, collection)
            if is_set:
                fields.append(setter.field)

        return TaggerResult(fields=fields)

    def log_results(self, results: dict[str, TaggerResult]) -> None:
        """Log the given tagger results"""
        header = "TAGGER RESULTS"
        table = TaggerResult.generate_table(results=results, header=header)

        self._logger.report(table)
        self._logger.print_line(REPORT)
