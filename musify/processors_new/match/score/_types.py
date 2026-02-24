from typing import Annotated, Union

from pydantic import Field

from musify.processors_new.match.score.numeric import LengthScorer, ReleaseYearScorer
from musify.processors_new.match.score.string import NameScorer, ArtistScorer, AlbumScorer

_scorer_classes = (NameScorer, ArtistScorer, AlbumScorer, LengthScorer, ReleaseYearScorer)
type LocalTrackType = Annotated[
    Union[*_scorer_classes],
    Field(discriminator="type"),
]
