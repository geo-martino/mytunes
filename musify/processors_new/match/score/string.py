from typing import Literal, Any, final, Self

from pydantic import Field, model_validator

from musify._types import LowerStrippedString
from musify.exception import MusifyValueError
from musify.models.exception import MusifyValidationError
from musify.models.item.album import HasAlbum
from musify.models.item.artist import HasArtists
from musify.models.properties.name import HasName
from musify.processors_new.clean.string import StringCleaner, NameCleaner, ArtistCleaner, AlbumCleaner
from musify.processors_new.match.score._base import Scorer


# noinspection PyAbstractClass
class StringScorer[CT: StringCleaner](Scorer[CT]):
    pass


# noinspection PyAbstractClass
class StringScoreReducer[CT: StringCleaner](StringScorer[CT]):
    reduce_on_phrases: set[LowerStrippedString] = Field(
        description=(
            "A set of phrases which, if found in one value but not the other and vice-versa, "
            "will reduce the name score by a factor of reduce_factor. "
        ),
        default_factory=set,
    )
    reduce_factor: float = Field(
        description=(
            "The factor by which to reduce the name score when certain phrases are found "
            "in the name of the item but not the other."
        ),
        default=1.0,
    )

    @model_validator(mode="after")
    def _validate_reduction_values(self) -> Self:
        if not self.reduce_on_phrases:
            return self
        if self.reduce_factor == 1:
            raise MusifyValidationError(
                "reduce_factor must be set to a value other than 1 when reduce_on_phrases is set"
            )
        return self

    def _reduce_score(self, score: int | float, value: str, other: str | None) -> float:
        if not value or not other:
            return score
        if not score or self.reduce_factor == 1 or not self.reduce_on_phrases:
            return score

        in_value_only = any(
            word in value.casefold().split() and word not in other.casefold().split() for word in self.reduce_on_phrases
        )
        in_other_only = any(
            word not in value.casefold().split() and word in other.casefold().split() for word in self.reduce_on_phrases
        )
        if in_value_only or in_other_only:
            score = max(score * self.reduce_factor, 0)

        return score


@final
class KaraokeScorer(StringScorer):
    """Score an item by checking whether its metadata indicates it is a karaoke track."""
    __final__ = True

    type: Literal["karaoke"] = "karaoke"

    cleaner: None = None
    karaoke_phrases: set[LowerStrippedString] = Field(
        description=(
            "A set of phrases which, if found in the metadata of a track, "
            "indicate that the track is a karaoke version."
        ),
        default={"karaoke", "instrumental", "backing track"}
    )
    prefer_not_karaoke: bool = Field(
        description=(
            "Whether to prefer non-karaoke versions of tracks over karaoke versions. "
            "If True, score 0 when item is karaoke and 1 when not karaoke. "
            "If False, score 1 when item is karaoke and 0 when not karaoke."
        ),
        default=True,
    )

    def can_score(self, item: Any) -> bool:
        return any((
            NameCleaner.can_clean(item),
            ArtistCleaner.can_clean(item),
            AlbumCleaner.can_clean(item),
        ))

    def score[T: HasName](self, item: T, other: T | None = None) -> int | float:
        scores = [
            self._calculate_score_for_name(item),
            self._calculate_score_for_artist(item),
            self._calculate_score_for_album(item)
        ]

        score = all(not is_karaoke for is_karaoke in scores) if self.prefer_not_karaoke else any(scores)
        return score * self.weight

    def _calculate_score(self, value: str | None, other: str | None = None) -> bool:
        if value is None:
            return False

        is_karaoke = any(phrase in value.casefold() for phrase in self.karaoke_phrases)
        return is_karaoke

    def _calculate_score_for_name(self, item: HasName) -> bool:
        if not isinstance(item, HasName):
            return False

        value = item.name
        score = self._calculate_score(value)

        self._log_score(item=item, result=score, item_val=value)
        return score

    def _calculate_score_for_artist(self, item: HasArtists) -> bool:
        if not isinstance(item, HasName) or not isinstance(item, HasArtists):
            return False

        value = item.artist
        score = self._calculate_score(value)

        self._log_score(item=item, result=score, item_val=value)
        return score

    def _calculate_score_for_album(self, item: HasName | HasAlbum) -> bool:
        if not not isinstance(item, HasName) or not isinstance(item, HasAlbum) or item.album is None:
            return False

        value = item.album.name
        score = self._calculate_score(value)

        self._log_score(item=item, result=score, item_val=value)
        return score


@final
class NameScorer(StringScoreReducer[NameCleaner]):
    """Score items by comparing names. Score=0 when either value is None."""
    __final__ = True

    type: Literal["name", "title"] = "name"
    cleaner: NameCleaner = NameCleaner()

    def _calculate_score(self, value: str, other: str | None) -> float:
        if not value or not other:
            return 0

        score = sum(word in other.split() for word in value.split()) / len(value.split())
        score = self._reduce_score(score, value=value, other=other)

        return score


@final
class ArtistScorer(StringScorer[ArtistCleaner]):
    """Score items by comparing artists. Score=0 when either value is None."""
    __final__ = True

    type: Literal["artist"] = "artist"
    cleaner: ArtistCleaner = ArtistCleaner()

    scale_on_many_artists: bool = Field(
        description=(
            "When many artists are present, a scale factor is applied to the score of matches on subsequent artists. "
            "i.e. match on artist 1 is scaled by 1, match on artist 2 is scaled by 1/2, "
            "match on artist 3 is scaled by 1/3 etc."
        ),
        default=True,
    )

    def _calculate_score(self, value: list[str], other: list[str] | None) -> float:
        if not value or not other:
            return 0

        score = 0
        other = " ".join(other)

        for i, artist in enumerate(value, 1):
            score_part = sum(word in other.split() for word in artist.split()) / len(artist.split())
            if self.scale_on_many_artists:
                score_part /= i

            score += score_part

        return score / len(value)


@final
class AlbumScorer(StringScoreReducer[AlbumCleaner]):
    """Score items by comparing album names. Score=0 when either value is None."""
    __final__ = True

    type: Literal["album"] = "album"
    cleaner: AlbumCleaner = AlbumCleaner()

    def _calculate_score(self, value: str, other: str) -> int | float:
        if not value or not other:
            return 0

        score = sum(word in other.split() for word in value.split()) / len(value.split())
        score = self._reduce_score(score, value=value, other=other)

        return score
