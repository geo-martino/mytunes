from collections.abc import Sequence, Iterable
from typing import Annotated, Self

from mytunes._types import TO_TUPLE
from mytunes.result import TotalCountResult, LenLogFormatter
from pydantic import Field

from ..._item.track import LocalTrack


class LibraryURIsResult[T: LocalTrack](TotalCountResult):
    """Stores the results of the URIs on loaded tracks in a local library."""
    _key_formatter = TotalCountResult._header_formatter

    source: str | None = Field(
        description="The remote library source these URIs are associated with.",
    )
    available: Annotated[
        Sequence[T],
        TO_TUPLE,
        LenLogFormatter(
            width=6, alignment="right", colour="red", colour_attributes=["bold"], condition=lambda x: x == 0
        ),
        LenLogFormatter(
            width=6, alignment="right", colour="green", colour_attributes=["bold"], condition=lambda x: x > 0
        ),
    ] = Field(
        description="The tracks which are available on this source i.e. the track has a matching URI set.",
        default_factory=tuple
    )
    missing: Annotated[
        Sequence[T],
        TO_TUPLE,
        LenLogFormatter(
            width=6, alignment="right", colour="blue", colour_attributes=["bold"], condition=lambda x: x == 0
        ),
        LenLogFormatter(
            width=6, alignment="right", colour="green", colour_attributes=["bold"], condition=lambda x: x > 0
        ),
    ] = Field(
        description=(
            "The tracks which are missing matching URIs "
            "i.e. it is unknown whether the track exists on this source or not."
        ),
        default_factory=tuple
    )
    unavailable: Annotated[
        Sequence[T],
        TO_TUPLE,
        LenLogFormatter(
            width=6, alignment="right", colour="green", colour_attributes=["bold"], condition=lambda x: x == 0
        ),
        LenLogFormatter(
            width=6, alignment="right", colour="red", colour_attributes=["bold"], condition=lambda x: x > 0
        ),
    ] = Field(
        description=(
            "The tracks which are confirmed to be unavailable on this source "
            "i.e. the track does not have a matching URI set because it doesn't exist on the remote library."
        ),
        default_factory=tuple
    )

    @classmethod
    def from_tracks(cls, tracks: Iterable[T], source: str | None = None) -> Self:
        """Create a result from the given tracks."""
        return cls(
            source=source,
            available=tuple(filter(lambda x: cls._is_available(x, source), tracks)),
            missing=tuple(filter(lambda x: cls._is_missing(x, source), tracks)),
            unavailable=tuple(filter(lambda x: cls._is_unavailable(x, source), tracks)),
        )

    @staticmethod
    def _is_available(track: T, source: str | None = None) -> bool:
        if source is None:
            return track.has_uri is True
        return any(uri.source.casefold() == source.casefold() and uri.exists for uri in track.uris)

    @staticmethod
    def _is_missing(track: T, source: str | None = None) -> bool:
        if source is None:
            return track.has_uri is None
        return all(uri.source.casefold() != source.casefold() for uri in track.uris)

    @staticmethod
    def _is_unavailable(track: T, source: str | None = None) -> bool:
        if source is None:
            return track.has_uri is False
        return any(uri.source.casefold() == source.casefold() and not uri.exists for uri in track.uris)
