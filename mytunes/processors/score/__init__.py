from ._base import Scorer

__all__ = [Scorer.__name__]

# must import all the supported formats here so that they are registered in the registry
from .numeric import LengthScorer, ReleaseYearScorer
from .string import NameScorer, ArtistScorer, AlbumScorer
