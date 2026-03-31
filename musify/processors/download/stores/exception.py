from musify.exception import MusifyError, MusifyTypeError


class StoreError(MusifyError):
    """Exception raised when store operations fail."""


class StoreTypeError(StoreError, MusifyTypeError):
    """Exception raised when an item type is invalid for a given store type."""
