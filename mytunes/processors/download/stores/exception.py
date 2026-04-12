from mytunes.exception import MyTunesError, MyTunesTypeError


class StoreError(MyTunesError):
    """Exception raised when store operations fail."""


class StoreTypeError(StoreError, MyTunesTypeError):
    """Exception raised when an item type is invalid for a given store type."""
