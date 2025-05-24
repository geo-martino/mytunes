from collections.abc import Iterable, Collection
from typing import Literal

import mutagen.id3
import mutagen.mp4
from PIL import Image
from pydantic import Field, AliasChoices, PositiveFloat, InstanceOf, field_validator

from musify.local.item.album import LocalAlbum
from musify.local.item.artist import LocalArtist
from musify.local.item.genre import LocalGenre
from musify.local.item.track import LocalTrack
from musify.model.properties.date import SparseDate
from musify.model.properties.image import ImageLink
from musify.model.properties.music import KeySignature
from musify.model.properties.order import Position


class M4A(LocalTrack[mutagen.mp4.MP4]):
    format: Literal["m4a"] = Field(
        description="The format (or file type) of the file.",
        validation_alias=AliasChoices("ext", "extension"),
        default=None,
        exclude=True,
    )

    name: str | None = Field(
        description="A title of this track.",
        default=None,
        validation_alias="©nam"
    )
    artists: list[LocalArtist] | None = Field(
        description="The artists featured on this track.",
        default=None,
        validation_alias="©ART"
    )
    album: LocalAlbum | None = Field(
        description="The album this track is featured on.",
        default=None,
        validation_alias="©alb"
    )
    # album_artist: list[LocalAlbum] | None = Field(
    #     default=None,
    #     validation_alias="aART"
    # )
    genres: list[LocalGenre] | None = Field(
        description="The genres associated with this track.",
        default=None,
        validation_alias=AliasChoices("----:com.apple.iTunes:GENRE", "©gen", "gnre")
    )
    track: Position | None = Field(
        description="The position of the track on the album that this track is featured on.",
        default=None,
        validation_alias="trkn"
    )
    disc: Position | None = Field(
        description="The position of the disc in the album that this track is featured on.",
        default=None,
        validation_alias="disk"
    )
    bpm: PositiveFloat | None = Field(
        description="The tempo of this track.",
        default=None,
        validation_alias="tmpo"
    )
    key: KeySignature | None = Field(
        description="The key of this track.",
        default=None,
        validation_alias="----:com.apple.iTunes:INITIALKEY"
    )
    released_at: SparseDate | None = Field(
        description="The date this track was released.",
        default=None,
        validation_alias="©day"
    )
    comments: list[str] = Field(
        description="Freeform comments that are associated with this track.",
        default_factory=list,
        validation_alias="©cmt"
    )
    images: dict[str, InstanceOf[Image.Image] | ImageLink] | None = Field(
        description="Images associated with this track.",
        default=None,
        validation_alias="covr"
    )
    # compilation: list[str] | None = Field(
    #     default=None,
    #     validation_alias="cpil"
    # )

    # noinspection PyNestedDecorators
    @field_validator("key", mode="before")
    @classmethod
    def _deserialize_free_form_field[T](cls, value: T) -> T | str:
        # parent class validators always execute after child class validators
        # need to manually call required upstream parent validators here
        value = cls._extract_first_value_from_sequence(value)
        if not isinstance(value, mutagen.mp4.MP4FreeForm):
            return value

        return value[:].decode()

    # noinspection PyNestedDecorators
    @field_validator("genres", mode="before")
    @classmethod
    def _deserialize_free_form_fields[T](cls, value: T) -> T | str:
        if not isinstance(value, tuple | list):
            return value
        return [cls._deserialize_free_form_field(v) for v in value]

    # noinspection PyNestedDecorators
    @field_validator("images", mode="before")
    @classmethod
    def _extract_first_image_from_sequence[T](cls, value: T | Iterable[T]) -> T:
        # AFAIK, MP4 only supports a single image per track
        # just extract the first one so downstream validators can handle it
        return cls._extract_first_value_from_sequence(value)
