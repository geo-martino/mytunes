from collections.abc import Sequence, Collection, Iterable
from typing import Union

from pydantic import AliasChoices, Field

from ._setter import Setter
from .._base import Processor
from musify.processors.filters import Filter
from ..._models import AttributeModel


class Tagger[IT: AttributeModel](Processor):
    item_filter: Union[Filter.annotation, None] = Field(
        default=None,
        validation_alias=AliasChoices("on", "filter"),
    )
    setters: Sequence[Setter.annotation] = Field(
        description="The setters to use to apply tag values to items.",
        validation_alias=AliasChoices("fields", "rules"),
    )

    def filter_items(self, items: Collection[IT]) -> Iterable[IT]:
        """Apply the item filter to the items provided (if applicable)."""
        if self.item_filter is None or not self.item_filter.ready:
            return items
        return filter(self.item_filter.check, items)

    def set_tags(self, item: IT, collection: Collection[IT]) -> None:
        """Apply setters to the item from the collection."""
        for setter in self.setters:
            setter.set(item, collection)
