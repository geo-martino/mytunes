"""
Exceptions relating to processor operations.
"""
from musify.exception import MusifyError


class ProcessorError(MusifyError):
    """Exception raised for errors related to processors."""


class ProcessorLookupError(ProcessorError):
    """Exception raised when processor name given is not valid."""


class ComparerError(ProcessorError):
    """Exception raised for errors related to :py:class:`Comparer` settings."""


class LimiterProcessorError(ProcessorError):
    """Exception raised for errors related to :py:class:`ItemLimiter` logic."""


class MatcherProcessorError(ProcessorError):
    """Exception raised for errors related to :py:class:`ItemMatcher` logic."""


class SorterProcessorError(ProcessorError):
    """Exception raised for errors related to :py:class:`ItemSorter` logic."""


class TimeMapperError(ProcessorError):
    """Exception raised for errors related to :py:class:`TimeMapper` logic."""


###########################################################################
## Filter errors
###########################################################################
class FilterError(ProcessorError):
    """Exception raised for errors related to :py:class:`Filter` logic."""
