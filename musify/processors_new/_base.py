"""
Base classes for all processors in this module. Also contains decorators for use in implementations.
"""
from musify.models import MusifyModel


class Processor(MusifyModel):
    """Generic base class for processors"""
    pass
