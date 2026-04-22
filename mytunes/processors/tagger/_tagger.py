from collections.abc import Sequence, Collection, Iterable, Mapping
from functools import partial
from typing import Union, Annotated, Self

from pydantic import AliasChoices, Field

from mytunes.core.properties.logger import HasLogger, HasProgress
from mytunes.processors.filters import Filter
from mytunes.result import Result, MapLogFormatter
from ._setter import Setter
from mytunes.processors import Processor
from ..._base.attribute import AttributeModel
from ..._base.resource import ResourceModel
from ..._types import TO_TUPLE
from ...core.properties.name import HasName
from ...logger import Logger


class TaggerResult[IT: AttributeModel](Result):
    item: IT = Field(
        description="The item with missing tags.",
    )
    tags: Annotated[
        Sequence[str],
        TO_TUPLE,
        MapLogFormatter(
            value=lambda values: Logger.format_list_to_string(values),
            colour="blue",
            colour_attributes=["bold"],
            include_name_in_log=False,
        ),
    ] = Field(
        description="The tags that were modified on the item.",
        default_factory=tuple
    )

    @classmethod
    def generate_table(
            cls,
            results: Sequence[Self] | Sequence[tuple[str | None, Self | None]] | Mapping[str | None, Self | None],
            header: str = None
    ) -> str:
        if isinstance(results, Mapping):
            return super().generate_table(results=results, header=header)

        results_mapped: list[tuple[str, TaggerResult]] = []
        for result in results:
            if not isinstance(result, TaggerResult):
                results_mapped.append(result)
                continue

            match result.item:
                case HasName():
                    key = result.item.name
                case ResourceModel() if result.item.unique_keys:
                    key = next(map(str, sorted(result.item.unique_keys, key=lambda k: isinstance(k, str))), None)
                case _:
                    key = str(id(result.item))

            results_mapped.append((key, result))

        return super().generate_table(results=results_mapped, header=header)


class Tagger[IT: AttributeModel](Processor, HasLogger, HasProgress):
    filter: Union[Filter.annotation, None] = Field(
        default=None,
        validation_alias="on",
    )
    setters: Sequence[Setter.annotation] = Field(
        description="The setters to use to apply tag values to items.",
        validation_alias=AliasChoices("fields", "rules"),
    )

    def set_tags_to_items(self, items: Iterable[IT]) -> tuple[TaggerResult[IT], ...]:
        """Apply setters to the item from the collection."""
        items = list(self.filter_items(items))

        task_id = self._progress.add_task(description="Applying tags to items", total=len(items))
        tasks = (partial(self.set_tags_to_item, item=item, collection=items) for item in items)
        results = tuple(self._run_tasks(tasks, task_id=task_id))

        return results

    def filter_items(self, items: Iterable[IT]) -> Iterable[IT]:
        """Apply the item filter to the items provided (if applicable)."""
        return filter(self.filter.check, items) if self.filter else items

    def set_tags_to_item(self, item: IT, collection: Collection[IT]) -> TaggerResult[IT]:
        """Apply setters to the item from the collection."""
        tags = []
        for setter in self.setters:
            is_set = setter.set(item, collection)
            if is_set:
                tags.append(setter.field)

        return TaggerResult(item=item, tags=tags)

    def log_results(self, results: Sequence[TaggerResult]) -> None:
        """Log the given tagger results"""
        header = "TAGGER RESULTS"
        table = TaggerResult.generate_table(results=results, header=header)

        self._logger.report(table, new_line_start=True, new_line_end=True)
