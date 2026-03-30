from musify.exception import MusifyError


class CheckFlowException(MusifyError):
    """Errors which are raised to control the flow of the check process, not to indicate an actual error."""


class QuitImmediately(CheckFlowException):
    pass


class SkipPage(CheckFlowException):
    pass
