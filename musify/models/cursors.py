from abc import abstractmethod
from collections.abc import MutableMapping, Mapping, Generator
from contextlib import suppress
from copy import deepcopy
from functools import total_ordering
from typing import ClassVar, Any, Self, Union, Annotated

from pydantic import Field, NonNegativeInt, model_validator, ValidationError, TypeAdapter, AliasPath, AliasChoices, \
    PositiveInt

from musify._types import String
from musify.exception import MusifyTypeError
from musify.models.exception import CursorError, CursorResponseError
from musify.models.remote import RemoteModel
from musify.models.url import HttpURL

_HTTP_ADAPTER = TypeAdapter(HttpURL)


# noinspection PyAbstractClass
@total_ordering
class PageCursor(RemoteModel):
    """A page cursor for paginated API responses."""
    url: HttpURL = Field(
        description="The URL for the current page",
        validation_alias="href",
    )
    total: NonNegativeInt | None = Field(
        description="The total number of items available from all pages.",
        default=None,
    )

    @model_validator(mode="before")
    @classmethod
    def _from_url[T](cls, value: T) -> T | dict[str, Any]:
        with suppress(ValidationError):
            url = _HTTP_ADAPTER.validate_python(value)
            value = dict(url=url)

        return value

    @classmethod
    def _set_param_value_from_url(cls, data: MutableMapping[str, Any], field_name: str, param_key: str) -> None:
        if not isinstance(data, MutableMapping):
            return

        url = cls._get_value_from_data(data=data, field_name="url")
        if url is None:
            return

        try:
            url = TypeAdapter(HttpURL).validate_python(url)
        except ValidationError:
            return

        url_value = url.query.get(param_key)
        inp_value = cls._get_value_from_data(data=data, field_name=field_name)
        if inp_value is not None or url_value is None:
            return

        data[field_name] = url_value

    def _set_param_value_to_url(self, key: str, value: Any) -> None:
        if value is None or self.url.query.get(key) == value:
            return

        if value is None or not str(value):
            url = self.url.without_query_params(key)
        else:
            url = self.url.update_query({key: value})

        if url != self.url:  # only set if different to avoid validation loops
            self.__dict__["url"] = url

    @property
    @abstractmethod
    def next(self) -> Self | None:
        """The cursor for the next page of items, if any."""
        raise NotImplementedError

    @classmethod
    def get_cursor_from_response(
            cls,
            response: Mapping[str, Any],
            path: str | AliasPath | AliasChoices | None = None,
    ) -> PageCursor:
        """
        Get the cursor from the given response data at the given path.

        Always attempts to find a cursor model at the given path - 1.
        So if the path is a string, it will just validate the response as is.
        This is because it is assumed that the path provided is the path to the items in the cursors
        at some lower level of the response, so the cursor itself should be at a higher level.
        """
        # avoid taking any subclasses of the InitialCursor since they will cause infinite loops
        # when trying to get the next page of items
        # noinspection PyTypeChecker
        classes = [
            kls for kls in PageCursor.registered_submodels
            if kls.source == cls.source and not issubclass(kls, InitialCursor)
        ]
        if not classes:
            raise CursorResponseError(f"No registered cursor models found for source {cls.source!r}.")

        # prioritise iterable cursors since they can be used for more efficient concurrent pagination
        classes.sort(key=lambda kls: issubclass(kls, IterablePageCursor), reverse=True)

        if len(classes) == 1:  # attempting to set union_mode fails on a single class
            adapter = TypeAdapter(classes[0])
        else:
            adapter = TypeAdapter(Annotated[Union[*classes], Field(union_mode="left_to_right")])

        return cls._create_cursor_from_response(response=response, path=path, adapter=adapter)

    @classmethod
    def _create_cursor_from_response[T: PageCursor](
            cls,
            response: Mapping[str, Any],
            path: str | AliasPath | AliasChoices | None,
            adapter: TypeAdapter[T],
    ) -> T:
        match path:
            case str() | None:
                return adapter.validate_python(response)

            case AliasPath() as alias:  # attempt to find cursor in response at path if it is not at the top level
                for key in alias.path:
                    with suppress(ValidationError):
                        return adapter.validate_python(response)

                    response = response[key]

            case AliasChoices() as choices:
                for alias in choices.choices:
                    with suppress(ValidationError, CursorResponseError):
                        return cls._create_cursor_from_response(response=response, path=alias, adapter=adapter)

        raise CursorResponseError(f"Could not find cursor in response at the given path: {path}.")

    def __lt__(self, other: Any) -> bool:
        return self.url < other.url


class HasPageCursor[CT: PageCursor](RemoteModel):
    cursor: CT = Field(
        description=(
            "The cursor for the current page of items. "
            "This is used for pagination and should be passed to the next page request to extend the model."
        )
    )


# noinspection PyAbstractClass
class ReversiblePageCursor(PageCursor):
    """A page cursor that can be reversed to produce the previous cursor."""
    @property
    @abstractmethod
    def previous(self) -> Self | None:
        """The cursor for the previous page of items, if any."""
        raise NotImplementedError


# noinspection PyAbstractClass
class IterablePageCursor(PageCursor):
    """
    A page cursor that can be iterated to produce all next cursors in advance.

    This can be used to produce all URLs for all pages in advance so that they can be requested concurrently.
    """
    @property
    def iter_pages(self) -> Generator[Self, None, None]:
        """Iteratively generate the next cursors for the next pages of items, if any."""
        cursor = self.next
        if cursor == self:
            raise CursorError("The next cursor is the same as the current cursor, which may cause an infinite loop.")

        while cursor is not None:
            yield cursor
            cursor = cursor.next

    @abstractmethod
    def reset(self, **kwargs) -> None:
        """Reset the current cursor to a previous page."""
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def sort_responses[T: dict[str, Any]](
            cls,
            responses: list[T],
            path: str | AliasPath | AliasChoices,
    ) -> list[Self]:
        """
        Sort the given responses in-place based on the current cursor.

        This is used to sort the responses from concurrent requests for all pages into the correct order.

        :param responses: The responses to sort.
        :param path: The path or path alias to the cursor in the response.
        :return: The sorted cursors for the responses, in the same order as the sorted responses.
        """
        raise NotImplementedError


# noinspection PyAbstractClass
class _HasLimitParam(PageCursor):
    _limit_param_key: ClassVar[str] = "limit"

    limit: NonNegativeInt | None = Field(
        description="The number of items to return per page.",
        default=None,
    )

    @model_validator(mode="before")
    @classmethod
    def _get_limit_from_url[T: MutableMapping[str, Any]](cls, data: T) -> T:
        cls._set_param_value_from_url(data, field_name="limit", param_key=cls._limit_param_key)
        return data

    @model_validator(mode="after")
    def _set_limit_to_url(self) -> Self:
        self._set_param_value_to_url(self._limit_param_key, self.limit)
        return self


class IndexCursor(IterablePageCursor, ReversiblePageCursor, _HasLimitParam):
    """
    A page cursor that uses index-based (or offset-based) pagination.
    
    The offset is the index of the first item in the current page of items.
    Pagination is achieved through the 'offset' to get the page of items at that index.

    The offset can be used to generate all pages in advance when the limit and total number of items are known.
    This allows for efficient concurrent pagination by generating all URLs for all pages in advance 
    and requesting them concurrently.
    """
    _offset_param_key: ClassVar[str] = "offset"

    offset: NonNegativeInt = Field(
        description="The starting offset of the current page of items.",
    )
    limit: NonNegativeInt = Field(
        description="The number of items to return.",
    )
    total: NonNegativeInt = Field(
        description="The total number of items available from all pages.",
    )

    @model_validator(mode="before")
    @classmethod
    def _get_params_from_url[T: MutableMapping[str, Any]](cls, data: T) -> T:
        cls._set_param_value_from_url(data, field_name="offset", param_key=cls._offset_param_key)
        return data

    @model_validator(mode="after")
    def _set_params_to_url(self) -> Self:
        self._set_param_value_to_url(self._offset_param_key, self.offset)
        return self

    @property
    def previous(self) -> Self | None:
        prev_offset = self.offset - self.limit
        if prev_offset < 0:
            return None

        url = self.url.update_query({self._offset_param_key: prev_offset, self._limit_param_key: self.limit})
        return type(self)(url=url, limit=self.limit, offset=prev_offset, total=self.total)

    @property
    def next(self) -> Self | None:
        """The cursor for the next page of items, if any."""
        next_offset = self.offset + self.limit
        if self.total == 0 or next_offset >= self.total:
            return None

        url = self.url.update_query(limit=self.limit, offset=next_offset)
        return type(self)(url=url, limit=self.limit, offset=next_offset, total=self.total)

    @property
    def iter_pages(self) -> Generator[Self, None, None]:
        """Iteratively generate the next cursors for the next pages of items, if any."""
        cursor = self.next
        while cursor is not None:
            yield cursor
            cursor = cursor.next

    def reset(self, offset: NonNegativeInt = 0) -> None:
        """Resets the cursor to the given offset. Handles negative offsets safely by setting the offset to 0."""
        self.offset = max(0, offset)

    @classmethod
    def sort_responses[T: dict[str, Any]](
            cls, responses: list[T], path: str | AliasPath | AliasChoices,
    ) -> list[Self]:
        cursors: list[Self] = [cls.get_cursor_from_response(response, path) for response in responses]
        if not all(isinstance(cursor, cls) for cursor in cursors):
            raise MusifyTypeError(f"All cursors in the responses must be {cls.__name__!r} types.")

        offsets = [cursor.offset for cursor in cursors]
        responses_copy = responses.copy()  # needed to avoid modifying the original list when sorting
        responses.sort(key=lambda response: offsets[responses_copy.index(response)])
        return sorted(cursors, key=lambda cursor: cursor.offset)


class KeyCursor(ReversiblePageCursor, _HasLimitParam):
    """
    A page cursor that uses key-based pagination.
    
    The key is usually some ID that identifies the first ID of the first result in a page.
    Pagination is then achieved through 'before' and 'after' parameters that specify 
    the key for the previous and next pages of items, respectively.
    """
    _before_param_key: ClassVar[str] = "before"
    _after_param_key: ClassVar[str] = "after"

    before: String | None = Field(
        description="The key to get the previous page of items",
        default=None,
    )
    after: String | None = Field(
        description="The key to get the next page of items",
        default=None,
    )

    @property
    def previous(self) -> Self | None:
        if self.before is None:
            return None
        url = self.url.update_query({self._after_param_key: self.before})
        return type(self)(url=url, limit=self.limit, total=self.total)

    @property
    def next(self) -> Self | None:
        if self.after is None:
            return None
        url = self.url.update_query({self._after_param_key: self.after})
        return type(self)(url=url, limit=self.limit, total=self.total)


class UrlCursor(PageCursor):
    """
    A page cursor that uses previous and next URLs for pagination.
    
    This is the most straightforward type of cursor, where the URLs for the previous and next pages are 
    provided directly in the response.
    This then means that you can only get the next page of items from the current page, 
    and cannot generate URLs for all pages in advance.
    """
    previous_url: HttpURL | None = Field(
        description="The URL for the previous page",
        default=None,
        validation_alias="previous",
    )
    next_url: HttpURL | None = Field(
        description="The URL for the next page",
        default=None,
        validation_alias="next",
    )

    @property
    def previous(self) -> Self | None:
        if self.previous_url is None:
            return None
        return type(self)(url=self.previous_url, next_url=self.url, total=self.total)

    @property
    def next(self) -> Self | None:
        if self.next_url is None:
            return None
        return type(self)(url=self.next_url, previous_url=self.url, total=self.total)


class InitialCursor(_HasLimitParam):
    """
    A page cursor that returns itself for the next page of items, and has no previous page.

    This is used in special cases where the type of cursor the API will return is now known in advance.
    For the pagination functions to work, the cursor must return a 'next' cursor to get the next page of items.
    If the user does not know the type of cursor the API will return in advance,
    they can use this cursor as a placeholder until they get the first page of items and can determine the type of
    cursor from the response.

    Special care must be taken to ensure that the API does not return a cursor of this same type for the next
    page of items, as this will cause an infinite loop when trying to get the next page of items.
    """

    @classmethod
    def from_url(cls, url: HttpURL, source: str, limit: PositiveInt | None = None) -> Self:
        """Generate an appropriate initial cursor for the given URL and source."""
        if cls.__final__:
            raise MusifyTypeError(
                "Cannot get an adapter for a final model, must be called on a base class with registered submodels"
            )

        # noinspection PyTypeChecker
        classes = [kls for kls in cls.registered_submodels if kls.source == source]
        if not classes:
            raise MusifyTypeError(f"No registered {cls.__name__} submodels found for source: {source!r}")

        return TypeAdapter(Union[*classes]).validate_python(dict(url=url, limit=limit))
    
    @property
    def next(self) -> Self | None:
        return deepcopy(self)
