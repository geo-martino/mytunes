from collections.abc import Sequence, Iterable, Mapping
from typing import Union, Annotated, Any

from pydantic import AliasChoices, Field, OnErrorOmit, validate_call

from mytunes.core.properties.logger import HasLogger, HasProgress
from mytunes.processors import Processor
from mytunes.processors.filters import Filter
from mytunes.result import ItemResult, MapLogFormatter
from ._setter import Setter
from ..._base.attribute import AttributeModel
from ...logger import Logger


class TaggerResult[IT: AttributeModel](ItemResult[IT]):
    tags: Annotated[
        Mapping[str, Any],
        MapLogFormatter(
            value=lambda values: Logger.format_list_to_string(values.keys()),
            style="bold blue",
            include_name_in_log=False,
        ),
    ] = Field(
        description="The tags that were modified on the item.",
        default_factory=dict
    )


class Tagger[IT: AttributeModel](Processor, HasLogger, HasProgress):
    filter: Union[Filter.annotation, None] = Field(
        default=None,
        validation_alias="on",
    )
    setters: Sequence[Setter.annotation] = Field(
        description="The setters to use to apply tag values to items.",
        validation_alias=AliasChoices("fields", "rules"),
    )

    @validate_call
    def set_tags_to_items(self, items: Iterable[OnErrorOmit[IT]]) -> tuple[TaggerResult[IT], ...]:
        """Apply setters to the item from the collection."""
        items = list(self.filter_items(items))

        task_id = self._progress.add_task(description="Applying tags to items", total=len(items) * len(self.setters))
        results: list[TaggerResult[IT]] = []

        for setter in self.setters:
            setter.set_context(items)

            for item in items:
                is_set = setter.set(item)
                self._progress.advance(task_id)

                result = next((result for result in results if result.item is item), None)
                if result is None:
                    result = TaggerResult(item=item)
                    results.append(result)

                if not is_set:
                    continue

                result.__dict__["tags"] = dict(result.tags) | {setter.field: getattr(item, setter.field)}

            setter.clear_context()

        self._progress.remove_task(task_id)

        return tuple(results)

    @validate_call
    def set_tags_to_item(self, item: IT, collection: Sequence[OnErrorOmit[IT]] = None) -> TaggerResult[IT]:
        """Apply setters to the item from the collection."""
        tags = []
        for setter in self.setters:
            if collection is not None:
                setter.set_context(collection)

            is_set = setter.set(item)
            if is_set:
                tags.append(setter.field)

            if collection is not None:
                setter.clear_context()

        return TaggerResult(item=item, tags=tags)

    @validate_call
    def filter_items(self, items: Iterable[OnErrorOmit[IT]]) -> Iterable[IT]:
        """Apply the item filter to the items provided (if applicable)."""
        return filter(self.filter.check, items) if self.filter else items

    @validate_call
    def log_results(self, results: Sequence[OnErrorOmit[TaggerResult]]) -> None:
        """Log the given tagger results"""
        header = "TAGGER RESULTS"
        table = TaggerResult.generate_table(results=results, header=header)

        self._logger.report(table, new_line_start=True)
