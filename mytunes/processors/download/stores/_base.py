import locale as locale_module
from abc import abstractmethod
from collections.abc import Sequence, Iterable, Collection, Mapping
from typing import ClassVar, Literal, Any, Union, get_args, Annotated, final, Self

from pydantic import Field, field_validator, validate_call, StringConstraints, TypeAdapter
from yarl import URL

from mytunes._types import StrippedString, HttpURL
from ...._models import BaseModel, ResourceModel
from ...._models import ModelMetaclass
from ...._models.properties.name import HasName
from mytunes.processors.clean.string import NameCleaner
from mytunes.processors.download.stores.exception import StoreError


class AudioStoreMetaclass(ModelMetaclass):
    @property
    def annotation(cls) -> Self:
        if not cls.registered_submodels:
            return cls
        return Annotated[
            super().annotation,
            Field(discriminator="name"),
        ]


# noinspection PyAbstractClass
class AudioStore[T: str](BaseModel, metaclass=AudioStoreMetaclass):
    """Formats the url for an online store for querying and purchasing audio files."""
    __final__ = False  # WORKAROUND: for typing on __init__
    _accepted_types: ClassVar[tuple[type[ResourceModel], ...]] = (ResourceModel,)

    def __init__(self, /, **data: Any) -> None:
        if not self.__final__:
            super().__init__(**data)
            return

        name = next(iter(get_args(type(self).model_fields["name"].annotation)))
        data.pop("name", None)
        super().__init__(name=name, **data)

    name: T = Field(
        description="The name of the store",
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

        query = self._format_query_for_item(item, fields=fields)
        if self.additional_query:
            query += f" {self.additional_query}"

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

            if value:
                query_parts.append(value)

        return " ".join(query_parts)

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


class HasLocale(BaseModel, metaclass=AudioStoreMetaclass):
    locale: Literal[*list(locale_module.locale_alias.values())] = Field(
        description="The locale of the store to access.",
        default=locale_module.getdefaultlocale()[0],
    )

    @field_validator("locale", mode="before", check_fields=True)
    @classmethod
    def _validate_locale_from_alias[T](cls, lc: T | str) -> T | str:
        if not isinstance(lc, str) or lc.casefold() not in list(locale_module.locale_alias.keys()):
            return lc
        return locale_module.normalize(lc)


_HTTP_ADAPTER = TypeAdapter(HttpURL)


@final
class GeneralAudioStore(AudioStore[Literal["general"]]):
    __final__ = True

    url: Annotated[StrippedString, StringConstraints(pattern=r"^[^{}]*\{\}[^{}]*$")] = Field(
        description=(
            "The template URL to open queries for. "
            "The given site should contain exactly 1 '{}' placeholder into which the processor can place "
            "a query for the item being searched. e.g. *bandcamp.com/search?q={}&item_type=t*"
        ),
    )

    @field_validator("url", mode="after", check_fields=True)
    @classmethod
    def _validate_url(cls, url: str) -> str:
        _HTTP_ADAPTER.validate_python(url.format(""))
        return url

    @validate_call
    def format_search_url(self, item: ResourceModel, fields: Sequence[str] = ()) -> URL:
        """Format the search URL for the given item"""
        if not fields:
            fields = self.fields
        if not fields:
            raise StoreError("No fields provided")

        query = self._format_query_for_item(item, fields=fields) + f" {self.additional_query}"
        return URL(self.url.format(query)).extend_query(self.additional_params)

    # ignored
    @property
    def _base_url(self) -> URL:
        return URL(self.url)

    # ignored
    def _format_query_path_for_item(self, item: ResourceModel, query: str) -> str:
        return super()._format_query_path_for_item(item, query=query)

    # ignored
    def _format_query_params_for_item(
            self, item: ResourceModel, query: str, fields: Collection[str]
    ) -> dict[str, str]:
        return super()._format_query_params_for_item(item, query=query, fields=fields)
