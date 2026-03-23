from collections.abc import Mapping
from typing import Annotated

from pydantic import Field

from musify.models.api import RemoteAPI, HasSavedEndpoints
from musify.models.api.playlist import HasPlaylistEndpoints, PlaylistReadWriteSavedEndpoints
from musify.models.properties.uri import HasURI
from musify.models.result import Result, LenLogFormatter
from musify.processors_new._base import InputProcessor


class CheckResult[T: HasURI](Result):
    """Stores the results of the searching process."""
    changed: Annotated[
        tuple[T, ...],
        LenLogFormatter(width=6, alignment="right", colour="blue", colour_attributes=["bold"], condition=lambda x: x == 0),
        LenLogFormatter(width=6, alignment="right", colour="green", colour_attributes=["bold"], condition=lambda x: x > 0),
    ] = Field(
        description="The items that had their matches changed during the check.",
        default_factory=tuple
    )
    unavailable: Annotated[
        tuple[T, ...],
        LenLogFormatter(width=6, alignment="right", colour="green", colour_attributes=["bold"], condition=lambda x: x == 0),
        LenLogFormatter(width=6, alignment="right", colour="yellow", colour_attributes=["bold"], condition=lambda x: x > 0),
    ] = Field(
        description="The items that were marked as unavailable during the check.",
        default_factory=tuple
    )
    skipped: Annotated[
        tuple[T, ...],
        LenLogFormatter(width=6, alignment="right", colour="green", colour_attributes=["bold"], condition=lambda x: x == 0),
        LenLogFormatter(width=6, alignment="right", colour="blue", colour_attributes=["bold"], condition=lambda x: x > 0),
    ] = Field(
        description="The items that were skipped during the check.",
        default_factory=tuple
    )


class Checker[API: RemoteAPI](InputProcessor):
    api: API | HasPlaylistEndpoints[HasSavedEndpoints[PlaylistReadWriteSavedEndpoints]] = Field(
        description="The API to use for checking matches.",
    )

    @property
    def source(self) -> str:
        """The name of the source that this searcher is searching on, derived from the API's source."""
        return self.api.source.title()

    ###########################################################################
    ## Logging
    ###########################################################################
    def log_results(self, results: Mapping[str, CheckResult]) -> None:
        """Log the given check results"""
        header = f"{self.source.upper()} CHECK RESULTS"
        table = CheckResult.generate_table(results=results, header=header)
        self.logger.report(table)