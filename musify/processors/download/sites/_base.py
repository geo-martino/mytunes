import locale as locale_module
from abc import abstractmethod
from collections.abc import Sequence, Iterable, Collection, Mapping
from typing import ClassVar, Literal, Any, Union
from urllib.parse import quote

from pydantic import Field, PrivateAttr, AliasChoices, field_validator, validate_call
from yarl import URL

from musify._types import StrippedString, String
from musify.models import BaseModel, abstract_property, ResourceModel
from musify.models.properties.name import HasName
from musify.processors.clean.string import NameCleaner
from musify.processors.download.sites.exception import StoreTypeError, StoreError


# noinspection PyAbstractClass
class AudioStore[T: str](BaseModel):
    """Formats the url for an online store for querying and purchasing audio files."""

    _accepted_types: ClassVar[tuple[type[ResourceModel], ...]] = (ResourceModel,)

    name: T = Field(
        description="The name of the download store",
        validation_alias=AliasChoices("store", "type"),
    )
    fields: Sequence[StrippedString] = Field(
        description="The fields to take from an item for use as the query string when opening sites.",
        default_factory=tuple,
    )
    cleaner: NameCleaner | None = Field(
        description=(
            "The cleaner to use for cleaning the query parameters generated for an item. "
            "If None, no cleaning will be done."
        ),
        default=None,
    )

    additional_query: StrippedString | None = Field(
        description="Additional string to add to the end of search query in the URL.",
        default=None,
    )
    additional_params: Mapping[str, str] = Field(
        description=(
            "Additional query parameters to add to the URL. "
            "WARNING: Will override any params generated from the item."
        ),
        default_factory=dict,
    )

    @property
    @abstractmethod
    def _base_url(self) -> URL:
        """The base url of the site"""
        raise NotImplementedError

    @validate_call
    def format_search_url(self, item: Union[_accepted_types], fields: Sequence[str] = ()) -> URL:
        """Format the search URL for the given item"""
        if not fields:
            fields = self.fields
        if not fields:
            raise StoreError("No fields provided")

        query = self._format_query_for_item(item, fields=fields) + f" {self.additional_query}"
        path = self._format_query_path_for_item(item, query=query)

        params = self._format_query_params_for_item(item, query=query, fields=fields)
        params |= self.additional_params

        return self._base_url.joinpath(path).update_query(params)

    def _format_query_for_item(self, item: Union[_accepted_types], fields: Iterable[str]) -> str:
        """Format the search query for the given item"""
        query_parts = []
        for field in fields:
            if (value := getattr(item, field, None)) is None:
                continue

            match value:
                case str() | HasName():
                    value = self._get_query_part(value)
                case list() | tuple() | set() | dict():
                    value = " ".join(val for val in map(self._get_query_part, value) if val)
                case _ if value is not None:
                    value = str(value)
                case _:
                    continue

            query_parts.append(value)

        return quote(" ".join(query_parts))

    def _get_query_part(self, item: Union[_accepted_types]) -> str | None:
        match item:
            case HasName():
                return self._get_query_part(item.name)
            case str() if self.cleaner is not None:
                return self.cleaner.clean(item)
            case str():
                return item
            case _:
                return None

    @abstractmethod
    def _format_query_path_for_item(self, item: Union[_accepted_types], query: str) -> str:
        """Format the path to the query page of the site"""
        raise NotImplementedError

    @abstractmethod
    def _format_query_params_for_item(
            self, item: Union[_accepted_types], query: str, fields: Collection[str]
    ) -> dict[str, str]:
        """Format the search query params for the given item"""
        raise NotImplementedError


class HasLocale(BaseModel):
    locale: Literal[*list(locale_module.locale_alias.values())] = Field(
        description="The locale of the store to access.",
        default_factory=lambda: locale_module.getdefaultlocale()[0],
    )

    @field_validator("locale", mode="before", check_fields=True)
    @classmethod
    def _validate_locale_from_alias[T](cls, lc: T | str) -> T | str:
        if not isinstance(lc, str) or lc not in list(locale_module.locale_alias.keys()):
            return lc
        return locale_module.normalize(lc)
