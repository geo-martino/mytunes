from typing import Annotated

from pydantic import Field

from mytunes.processors.filters.composite import GroupResult, CompositeResult
from mytunes.result import LenLogFormatter, CountResult, LogPosition, NamedResult
from ..._item.track import LocalTrack


class LimitResult(CountResult):
    limited: Annotated[
        tuple[LocalTrack, ...],
        LogPosition(position=20),
        LenLogFormatter(width=6, alignment="right", colour="blue", colour_attributes=["bold"]),
    ] = Field(
        description="The items after applying limiting.",
        default_factory=tuple,
    )
    limit_ignored: Annotated[
        tuple[LocalTrack, ...],
        LogPosition(position=21),
        LenLogFormatter(width=6, alignment="right", colour="blue", colour_attributes=["bold"]),
    ] = Field(
        description="The items that were ignored while applying limiting.",
        default_factory=tuple,
    )


class SortResult(CountResult):
    sorted: Annotated[
        tuple[LocalTrack, ...],
        LogPosition(position=30),
        LenLogFormatter(width=6, alignment="right", colour="blue", colour_attributes=["bold"]),
    ] = Field(
        description="The items after applying sorting.",
        default_factory=tuple,
    )


class LoadPlaylistResult(NamedResult, GroupResult[LocalTrack], LimitResult):
    tracks: Annotated[
        tuple[LocalTrack, ...],
        LogPosition(position=50),
        LenLogFormatter(
            width=6, alignment="right", colour="red", colour_attributes=["bold"], condition=lambda x: x == 0
        ),
        LenLogFormatter(
            width=6, alignment="right", colour="green", colour_attributes=["bold"], condition=lambda x: x > 0
        ),
    ] = Field(
        description="The final list of tracks after all operations.",
        default_factory=tuple,
    )

    @classmethod
    def from_results(
            cls,
            name: str,
            match: CompositeResult[LocalTrack] | None = None,
            limit: LimitResult | None = None,
            sort: SortResult | None = None,
    ) -> LoadPlaylistResult:
        """Create the result by combining the results from the various playlist load stages."""
        match = {key: val for key, val in (match.__dict__ or {}).items() if not key.startswith("_")}
        limit = {key: val for key, val in (limit.__dict__ or {}).items() if not key.startswith("_")}
        # just take the sorted list as the final tracks as that's always the last step in the load
        return cls(name=name, **match, **limit, tracks=sort.sorted)


class SavePlaylistResult(NamedResult, CountResult):
    """The result of saving a playlist."""
    pass
