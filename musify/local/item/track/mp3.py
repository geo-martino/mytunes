from collections.abc import MutableSequence, MutableMapping, Iterable, Collection
from typing import Any, Literal

import mutagen.id3
import mutagen.mp3
from PIL import Image
from pydantic import Field, AliasChoices, PositiveFloat, InstanceOf, model_validator, field_validator, field_serializer, \
    model_serializer
from pydantic_core.core_schema import SerializerFunctionWrapHandler, FieldSerializationInfo, SerializationInfo

from musify.local.item.album import LocalAlbum
from musify.local.item.artist import LocalArtist
from musify.local.item.genre import LocalGenre
from musify.local.item.track import LocalTrack
from musify.model.properties.date import SparseDate
from musify.model.properties.image import ImageLink, get_picture_name_from_id3_value
from musify.model.properties.music import KeySignature
from musify.model.properties.order import Position


class MP3(LocalTrack[mutagen.mp3.MP3]):
    format: Literal["mp3"] = Field(
        description="The format (or file type) of the file.",
        validation_alias=AliasChoices("ext", "extension"),
        default=None,
        exclude=True,
    )

    name: str | None = Field(
        description="A title of this track.",
        default=None,
        alias="TIT2",
    )
    artists: list[LocalArtist] | None = Field(
        description="The artists featured on this track.",
        default=None,
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
    genres: list[LocalGenre] | None = Field(
        description="The genres associated with this track.",
        default=None,
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
    images: dict[str, InstanceOf[Image.Image] | ImageLink] | None = Field(
        description="Images associated with this track.",
        default=None,
        alias="APIC",
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
    @model_validator(mode="before")
    @classmethod
    def _merge_suffixed_tags[T](cls, data: T) -> T | dict[str, Any]:
        # parent class validators always execute after child class validators
        # need to manually call required upstream parent validators here
        # noinspection PyCallingNonCallable
        data = cls._extract_tags_from_mutagen(data)
        if not isinstance(data, MutableMapping):
            return data

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

        return data

    # noinspection PyNestedDecorators
    @model_serializer(mode="wrap")
    def _expand_suffixable_tag_keys(
            self, handler: SerializerFunctionWrapHandler, info: SerializationInfo
    ) -> dict[str, Any]:
        data = handler(self)
        if not info.by_alias:  # not serializing to tag IDs
            return data

        for tag_id, tag_value in data.copy().items():
            if not isinstance(tag_value, tuple | list):
                continue

            for i, frame in enumerate(tag_value, 1):
                match frame:
                    case mutagen.id3.COMM():
                        tag_parts = (tag_id, frame.desc or str(i), frame.lang or None)
                    case mutagen.id3.APIC():
                        tag_type = get_picture_name_from_id3_value(frame.type) if frame.type is not None else str(i)
                        tag_parts = (tag_id, tag_type)
                    case _:
                        tag_parts = (tag_id,)
                print(tag_parts)
                data[":".join(filter(None, tag_parts))] = frame

            data.pop(tag_id)

        return data

    # noinspection PyNestedDecorators
    @field_validator(
        "name", "album", "track", "disc", "bpm", "key", "released_at", "uri",
        mode="before"
    )
    @classmethod
    def _deserialize_text_frame[T](cls, value: T | Iterable[T]) -> T | str:
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
    def _deserialize_text_frames[T](cls, value: T | Iterable[T]) -> T | list[str]:
        if value is None:
            return value
        if not isinstance(value, tuple | list):
            value = [value]

        return [cls._deserialize_text_frame(v) for v in value]

    # noinspection PyNestedDecorators
    @field_serializer(
        "name", "artists", "album", "genres", "track", "disc", "bpm", "key", "released_at",
        mode="plain", when_used="unless-none"
    )
    def _serialize_text_frame(self, value: Any, info: FieldSerializationInfo) -> InstanceOf[mutagen.id3.TextFrame]:
        if not isinstance(value, tuple | list):
            value = [value]

        frame_cls = self._get_frame_class(info)
        tag_value = self._join_split_tags(value)
        return frame_cls(text=tag_value)

    @field_serializer("comments", mode="plain")
    def _serialize_text_frames(self, value: Any, info: FieldSerializationInfo) -> list[InstanceOf[mutagen.id3.TextFrame]]:
        frame_cls = self._get_frame_class(info)

        value = [frame_cls(text=item) for item in value]
        if self.uri is not None and info.context and info.context.get("uri") == info.field_name:
            value.append(frame_cls(text=str(self.uri), desc=f"{self.uri.source}URI"))

        return value

    # noinspection PyNestedDecorators
    @field_validator("images", mode="before")
    @classmethod
    def _deserialize_images_from_apic_frames[T](
            cls, frames: T | bytes | mutagen.id3.APIC | Collection[mutagen.id3.APIC]
    ) -> T | dict[int, bytes]:
        if isinstance(frames, mutagen.id3.APIC):
            frames = [frames]
        if not isinstance(frames, tuple | list):
            return frames
        elif not all(isinstance(img, mutagen.id3.APIC) for img in frames):
            return frames

        return {attr.type: attr.data for attr in frames}

    # noinspection PyTypeChecker
    # noinspection PyNestedDecorators
    @field_serializer("images", mode="plain", when_used="unless-none")
    def _serialize_images(
            self, images: MutableMapping[str, InstanceOf[Image.Image] | ImageLink], info: FieldSerializationInfo
    ) -> list[InstanceOf[mutagen.id3.APIC]]:
        if not info.by_alias:  # if not serializing to tag IDs, return the images as bytes
            return super()._serialize_images(images)

        return [
            mutagen.id3.APIC(
                encoding=mutagen.id3.Encoding.UTF8,
                mime=Image.MIME[images[kind].format],
                type=getattr(mutagen.id3.PictureType, kind.upper().replace(" ", "_")),
                data=image,
            )
            for kind, image in super()._serialize_images(images).items()
        ]
