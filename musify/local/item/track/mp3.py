from collections.abc import MutableSequence, MutableMapping, Iterable, Sequence
from copy import copy
from typing import Any, ClassVar, Self

import mutagen.id3
import mutagen.mp3
from PIL import Image, ImageFile as PILImageFile
from pydantic import Field, AliasChoices, PositiveFloat, InstanceOf, model_validator, model_serializer, \
    field_validator, field_serializer, ModelWrapValidatorHandler
from pydantic_core.core_schema import SerializerFunctionWrapHandler, FieldSerializationInfo, SerializationInfo

from musify.local.item.album import LocalAlbum
from musify.local.item.artist import LocalArtist
from musify.local.item.genre import LocalGenre
from musify.local.item.track import LocalTrack
from musify.local.item.track._base import TagDumpContext
from musify.models.properties.date import SparseDate
from musify.models.properties.image import ImageURL, ImageFile
from musify.models.properties.music import KeySignature
from musify.models.properties.name import HasName
from musify.models.properties.order import Position


class MP3(LocalTrack[mutagen.mp3.MP3]):
    __supported_extensions__ = frozenset({"mp3"})

    class EmbeddedImage(LocalTrack.EmbeddedImage[mutagen.mp3.MP3, mutagen.id3.APIC]):
        alias: ClassVar[str] = "APIC"

        @classmethod
        def _get_bytes(cls, value: Any) -> Any:
            return value.data if isinstance(value, mutagen.id3.APIC) else value

        @classmethod
        def get_id3_type_from_tag(cls, value: mutagen.id3.APIC) -> str | None:
            if not isinstance(value, mutagen.id3.APIC):
                return
            return cls._get_type_from_number(int(value.type))

        def build(self, image: bytes | PILImageFile.ImageFile | None) -> mutagen.id3.APIC | None:
            if image is None:
                return

            image, data = self._get_image_data(image)
            return mutagen.id3.APIC(
                encoding=mutagen.id3.Encoding.UTF8,
                mime=Image.MIME[image.format],
                type=self.id3_type,
                data=data,
            )

    name: str | None = Field(
        description="A title of this track.",
        default=None,
        alias="TIT2",
    )
    artists: list[LocalArtist] = Field(
        description="The artists featured on this track.",
        default_factory=list,
        alias="TPE1",
    )
    album: LocalAlbum | None = Field(
        description="The album this track is featured on.",
        default=None,
        alias="TALB",
    )
    # album_artist: LocalArtist | None = Field(
    #     default=None,
    #     alias="TPE2",
    # )
    genres: list[LocalGenre] = Field(
        description="The genres associated with this track.",
        default_factory=list,
        alias="TCON",
    )
    track: Position | None = Field(
        description="The position of the track on the album that this track is featured on.",
        default=None,
        alias="TRCK",
    )
    disc: Position | None = Field(
        description="The position of the disc in the album that this track is featured on.",
        default=None,
        alias="TPOS",
    )
    bpm: PositiveFloat | None = Field(
        description="The tempo of this track.",
        default=None,
        alias="TBPM",
    )
    key: KeySignature | None = Field(
        description="The key of this track.",
        default=None,
        alias="TKEY",
    )
    released_at: SparseDate | None = Field(
        description="The date this track was released.",
        default=None,
        validation_alias=AliasChoices("TDAT", "TDOR", "TYER", "TORY", "TDRC"),
        serialization_alias="TDAT",
    )
    rating: float | None = Field(
        description="The rating of this track.",
        default=None,
        alias="POPM",
    )
    comments: list[str] = Field(
        description="Freeform comments that are associated with this track.",
        default_factory=list,
        validation_alias=AliasChoices("COMM", "COMMENT"),
        serialization_alias="COMM",
    )
    images: MutableMapping[str, ImageFile | ImageURL | EmbeddedImage] | None = Field(
        description="Images associated with this track.",
        default=None,
        alias=EmbeddedImage.alias,
    )
    # compilation: list[str] | None = Field(
    #     default=None,
    #     alias="TCMP",
    # )

    @classmethod
    def _get_frame_class(cls, info: FieldSerializationInfo) -> type[mutagen.id3.Frame]:
        tag_id = cls._get_tag_id(info.field_name)
        return getattr(mutagen.id3, tag_id)

    # noinspection PyNestedDecorators
    @model_validator(mode="wrap")
    @staticmethod
    def _merge_suffixed_tags(file: mutagen.mp3.MP3, handler: ModelWrapValidatorHandler[Self]) -> Self:
        if not isinstance(file, mutagen.mp3.MP3):
            return handler(file)

        data = dict(file.tags)
        for key in list(data):
            key_prefix = key.split(":")[0]
            if key_prefix.startswith("COMM"):  # special case to merge comment keys correctly
                key_prefix = "COMM"
            if key_prefix == key:
                continue

            if key_prefix not in data:
                data[key_prefix] = []
            elif not isinstance(val_prefix := data[key_prefix], MutableSequence):
                data[key_prefix] = [val_prefix]

            data[key_prefix].append(data.pop(key))

        return handler(data)

    # noinspection PyNestedDecorators
    @model_serializer(mode="wrap")
    def _format_to_tags(
            self, handler: SerializerFunctionWrapHandler, info: SerializationInfo
    ) -> dict[str, Any]:
        data = handler(self)
        if not info.by_alias or not isinstance(data, MutableMapping):  # not serializing to tag IDs
            return data

        for tag_id, tag_value in copy(data).items():
            if not isinstance(tag_value, tuple | list):
                continue

            for i, frame in enumerate(tag_value, 1):
                match frame:
                    case mutagen.id3.COMM():
                        tag_parts = (tag_id, frame.desc or str(i), frame.lang or None)
                    case mutagen.id3.APIC():
                        tag_type = next(
                            (name for name, enum in vars(mutagen.id3.PictureType).items() if enum == frame.type), str(i)
                        )
                        tag_parts = (tag_id, tag_type)
                    case _:
                        tag_parts = (tag_id,)

                data[":".join(filter(None, tag_parts))] = frame

            data.pop(tag_id)

        return data

    # noinspection PyNestedDecorators
    @field_validator(
        "name", "album", "track", "disc", "bpm", "key", "released_at", "uri",
        mode="before"
    )
    @classmethod
    def _deserialize_text_frame(cls, value: mutagen.id3.TextFrame | Sequence[mutagen.id3.TextFrame]) -> str:
        # parent class validators always execute after child class validators
        # need to manually call required upstream parent validators here
        value = cls._extract_first_value_from_single_sequence(value)
        if not isinstance(value, mutagen.id3.TextFrame):
            return value

        return str(value)

    # noinspection PyNestedDecorators
    @field_validator(
        "artists", "genres", "comments",
        mode="before"
    )
    @classmethod
    def _deserialize_text_frames(cls, value: Iterable[mutagen.id3.TextFrame]) -> list[str]:
        if value is None:
            return value
        if not isinstance(value, tuple | list):
            value = [value]

        return list(map(cls._deserialize_text_frame, value))

    # noinspection PyNestedDecorators
    @field_validator("rating", mode="before")
    @classmethod
    def _deserialize_rating_frame(cls, value: mutagen.id3.POPM | Sequence[mutagen.id3.POPM]) -> str:
        value = cls._extract_first_value_from_single_sequence(value)
        if not isinstance(value, mutagen.id3.POPM):
            return value

        # noinspection PyUnresolvedReferences
        return value.rating

    @field_serializer("album", mode="plain", when_used="unless-none")
    def _serialize_name(self, value: str | HasName, info: SerializationInfo) -> str | InstanceOf[mutagen.id3.TextFrame]:
        if info.mode == "json":
            return self._extract_name(value)
        return self._serialize_text_frame(value, info=info)

    @field_serializer("artists", "genres", mode="plain", when_used="unless-none")
    def _serialize_names(
        self, value: Iterable[str | HasName], info: SerializationInfo
    ) -> list[str] | InstanceOf[mutagen.id3.TextFrame]:
        if info.mode == "json":
            return self._extract_names(value)
        return self._serialize_text_frame(value, info=info)

    # noinspection PyNestedDecorators
    @field_serializer(
        "name", "track", "disc", "bpm", "key", "released_at",
        mode="plain", when_used="unless-none"
    )
    def _serialize_text_frame(self, value: str | HasName, info: FieldSerializationInfo) -> InstanceOf[mutagen.id3.TextFrame]:
        if not info.by_alias or info.mode == "json":  # not serializing to tag IDs
            return value
        if not isinstance(value, tuple | list):
            value = [value]

        frame_cls = self._get_frame_class(info)
        tag_value = self._join_split_tags(value)
        return frame_cls(text=tag_value)

    @field_serializer("comments", mode="plain", when_used="unless-none")
    def _serialize_text_frames(
            self, values: Iterable[str | HasName], info: FieldSerializationInfo
    ) -> list[InstanceOf[mutagen.id3.TextFrame]]:
        if not info.by_alias or info.mode == "json":  # not serializing to tag IDs
            return values

        frame_cls = self._get_frame_class(info)
        values: list[frame_cls] = [frame_cls(text=item, lang="eng") for item in values]

        context = info.context
        if self.uris and isinstance(context, TagDumpContext) and context.map_uri_to_tag == info.field_name:
            values.extend(frame_cls(text=str(uri), desc=f"{uri.source}URI", lang="eng") for uri in self.uris)

        return values

    @staticmethod
    def _clear_tag(file: mutagen.mp3.MP3, tag_id: str) -> set[str]:
        removed = set()
        for tag_key in file.tags:
            if tag_key.casefold().startswith(tag_id.casefold()):
                del file.tags[tag_key]
                removed.add(tag_key)

        return removed
