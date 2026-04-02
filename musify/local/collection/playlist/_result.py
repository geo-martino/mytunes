from typing import Annotated

from pydantic import Field

from musify.local.item.track import LocalTrack
from musify.models.result import LenLogFormatter, CountResult, LogPosition
from musify.processors.filters.composite import GroupResult, CompositeFilter, CompositeResult


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


class LoadPlaylistResult(GroupResult[LocalTrack], LimitResult, SortResult):
    @property
    def tracks(self) -> tuple[LocalTrack, ...]:
        """Return the final list of tracks after a load operation."""
        # sorting is the last stage of the load process so it will provide the final result
        return self.sorted

    @classmethod
    def from_results(
            cls,
            match: CompositeResult[LocalTrack] | None = None,
            limit: LimitResult | None = None,
            sort: SortResult | None = None,
    ) -> LoadPlaylistResult:
        """Create the result by combining the results from the various playlist load stages."""
        match = {key: val for key, val in (match.__dict__ or {}).items() if not key.startswith("_")}
        limit = {key: val for key, val in (limit.__dict__ or {}).items() if not key.startswith("_")}
        sort = {key: val for key, val in (sort.__dict__ or {}).items() if not key.startswith("_")}
        return cls(**match, **limit, **sort)


class SavePlaylistResult(CountResult):
    """The result of saving a playlist."""
    pass
