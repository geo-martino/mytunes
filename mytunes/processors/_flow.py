from mytunes.exception import MyTunesError


class ProcessorFlowException(MyTunesError):
    """Errors which are raised to control the flow of a processor, not to indicate an actual error."""


class QuitImmediately(ProcessorFlowException):
    pass


class SkipPage(ProcessorFlowException):
    pass
