import itertools
from abc import abstractmethod
from collections.abc import Collection, Mapping, MutableMapping, MutableSequence, Iterable, Sequence
from copy import copy
from io import BytesIO
from pathlib import Path
from typing import Self, Any, Literal, ClassVar

import aiofiles
import mutagen
import mutagen.id3
from PIL import Image, ImageFile as PILImageFile
from mutagen import FileType
from pydantic import field_validator, model_validator, validate_call, AliasChoices, ModelWrapValidatorHandler, \
    InstanceOf, field_serializer
# noinspection PyProtectedMember
from pydantic.fields import Field, FieldInfo
from pydantic_core.core_schema import FieldSerializationInfo

from musify.local._base import LocalModel
from musify.local.exception import FileError, TagError
from musify.local.item.album import LocalAlbum
from musify.local.item.artist import LocalArtist
from musify.local.item.genre import LocalGenre
from musify.models import BaseModel
from musify.models.collection.library import Library
from musify.models.item.track import Track, HasMutableTracks
from musify.models.properties.audio import IsAudioFile
from musify.models.properties.date import HasAddedDate, HasPlayedDate
from musify.models.properties.file import IsReadableFile, IsWriteableFile, IsLocalFile
from musify.models.properties.image import FileEmbeddedImage, ImageSource
from musify.models.properties.logger import HasLogger
from musify.models.properties.name import HasName
from musify.models.properties.order import Position
from musify.models.properties.uri import HasMutableURI, URI


class TagDumpContext[T](BaseModel):
    map_uri_to_tag: Literal["comments"] = Field(
        description="The tag to use for storing the URIs of the track.",
        default="comments"
    )
    loaded_images: Mapping[str, InstanceOf[PILImageFile.ImageFile]] = Field(
        description="The image properties and their loaded images.",
        default_factory=dict
    )


# noinspection PyAbstractClass
class LocalAudioFile(IsAudioFile, IsReadableFile, IsWriteableFile, IsLocalFile):
    @classmethod
    def _extract_tags_from_mutagen(cls, file: mutagen.FileType):
        data = IsLocalFile._extract_tags_from_mutagen(file)
        data |= IsAudioFile._extract_tags_from_mutagen(file)
        return data


class LocalTrack[FT: FileType](
    LocalModel,
    Track[LocalArtist, LocalAlbum, LocalGenre, URI],
    LocalAudioFile,
    HasMutableURI[URI],
    HasAddedDate,
    HasPlayedDate,
):
    __tag_fields__ = frozenset(set(Track.model_fields.keys()) - {"uri"} | {"compilation"})

    # noinspection PyAbstractClass
    class EmbeddedImage[TT](FileEmbeddedImage):
        alias: ClassVar[str | AliasChoices] = "images"

        # noinspection PyNestedDecorators
        @model_validator(mode="wrap")
        @classmethod
        def _from_tag_value(cls, value: TT, handler: ModelWrapValidatorHandler[Self]) -> Self:
            img_bytes = cls._get_bytes(value)
            if not isinstance(img_bytes, bytes):
                return handler(value)

            img = Image.open(BytesIO(img_bytes))
            obj = handler(img)
            del img

            img_type = cls.get_id3_type_from_tag(value)
            if img_type:
                obj.type = img_type
            return obj

        @classmethod
        def from_image_model(cls, model: ImageSource) -> Self:
            """Create an instance of this image models from any other type of ImageSource models."""
            if isinstance(model, cls):
                return model

            # noinspection PyTypeChecker
            dump = model.model_dump(
                include=set(model.__class__.model_fields) & set(cls.model_fields),
                exclude_none=True,
                exclude_defaults=True,
                exclude_unset=True
            )
            return cls(**dump)

        async def _get_file(self, file: FT = None) -> FT:
            if isinstance(file, mutagen.FileType):
                if self.path is not None and Path(file.filename or "") != self.path:
                    raise FileError("Given file does not match the path of this image.")
                return file

            if self.path is None:
                raise FileError("Path is not set and no loaded file was given, cannot load image.")
            return await LocalTrack.load_file(self.path)

        async def _get_tag_value(self, file: FT = None) -> Any:
            file = await self._get_file(file)
            return file.tags.get(self.alias)

        @staticmethod
        def _get_image_data(image: bytes | PILImageFile.ImageFile) -> tuple[PILImageFile.ImageFile, bytes]:
            if isinstance(image, bytes):
                data = image
                image = Image.open(BytesIO(data))
            else:
                data = BytesIO()
                image.save(data, format=image.format)
                data = data.getvalue()

            return image, data

        @classmethod
        @abstractmethod
        def _get_bytes[T](cls, value: T | TT) -> T | bytes | None:
            raise NotImplementedError

        @classmethod
        @abstractmethod
        def get_id3_type_from_tag(cls, value: TT) -> str | None:
            """Get the ID3 type from the given attribute."""
            raise NotImplementedError

        async def load(self, file: FT = None) -> PILImageFile.ImageFile | None:
            for attr in await self._get_tag_value(file):
                id3_type = self.get_id3_type_from_tag(attr)
                if id3_type == self.type:
                    img_bytes = self._get_bytes(attr)
                    return Image.open(BytesIO(img_bytes))

        @abstractmethod
        def build(self, image: bytes | PILImageFile.ImageFile | None) -> TT:
            """Builds the image tag object for serialization."""
            raise NotImplementedError

    ###########################################################################
    ## Utility Methods
    ###########################################################################
    @classmethod
    @validate_call
    async def from_path(cls, path: str | Path) -> Self:
        file = await cls.load_file(path)
        # some subclasses need to access the file obj on construction so just pass the file obj
        # noinspection PyArgumentList
        return cls.model_validate(file)

    @classmethod
    @validate_call
    async def load_file(cls, path: str | Path) -> FT:
        # TODO: improve async performance?
        async with aiofiles.open(path, mode='rb') as file:
            file = mutagen.File(await file.read())
            file.filename = str(path)

        return file

    @classmethod
    def _get_tag_id(cls, name: str) -> str | None:
        field: FieldInfo = cls.model_fields[name]
        tag_id = None
        if isinstance(field.serialization_alias, str):
            tag_id = field.serialization_alias
        elif isinstance(field.alias, str):
            tag_id = field.alias
        elif isinstance(field.validation_alias, str):
            tag_id = field.validation_alias
        elif isinstance(field.validation_alias, AliasChoices):
            tag_id = next(iter(field.validation_alias.choices))

        return tag_id

    @staticmethod
    def _get_ext_from_input(value: Any) -> str:
        if isinstance(value, mutagen.FileType):
            value = Path(value.filename)
        return super().get_ext_from_input(value)

    ###########################################################################
    ## Validators/Serializers
    ###########################################################################
    @classmethod
    def _extract_tags_from_mutagen(cls, file: mutagen.FileType) -> dict[str, Any]:
        """Extract tags from a mutagen file object."""
        data = dict(file.tags) | super()._extract_tags_from_mutagen(file)
        return data

    # noinspection PyNestedDecorators
    @field_validator(
        "name", "album", "bpm", "key", "uri", "rating",
        mode="before", check_fields=True
    )
    @staticmethod
    def _extract_first_value_from_sequence[T](value: Sequence[T]) -> T:
        if isinstance(value, tuple | list) and len(value) >= 1:
            value = value[0]
        return value

    # noinspection PyNestedDecorators
    @field_validator(
        "name", "album", "track", "disc", "bpm", "key", "released_at", "uri",
        mode="before", check_fields=True
    )
    @staticmethod
    def _extract_first_value_from_single_sequence[T](value: Sequence[T]) -> T:
        if isinstance(value, tuple | list) and len(value) == 1:
            value = value[0]
        return value

    # noinspection PyNestedDecorators
    @field_validator(
        "name", "album", "track", "disc", "bpm", "key", "released_at", "uri",
        mode="before", check_fields=True
    )
    @staticmethod
    def _nullify[T](value: T) -> T | None:
        match value:
            case Collection() if len(value) == 0:
                return
            case Collection() if all(isinstance(v, str) and not v for v in value):
                return
            case _:
                return value

    # noinspection PyNestedDecorators
    @field_validator(
        "genres", "comments",
        mode="before", check_fields=True
    )
    @classmethod
    def _split_joined_tags[T: str](cls, value: T) -> T | list[str]:
        if not isinstance(value, tuple | list) or not all(isinstance(v, str) for v in value):
            return value
        return list(itertools.chain.from_iterable(map(cls._separate_tags, value)))

    @classmethod
    def _join_split_tags(cls, value: Iterable[Any]) -> str:
        values = map(cls._extract_name, value)
        return cls._join_tags(str(v) for v in values if v and str(v))

    @staticmethod
    def _extract_name(value: str | HasName) -> str | None:
        if not isinstance(value, HasName):
            return value
        return value.name if value is not None else None

    def _extract_names[T: Iterable[str | HasName]](self, values: T) -> T | list[str]:
        if not isinstance(values, Iterable):
            return values

        values = list(map(self._extract_name, values))
        return values

    def _serialize_position_tags[T: Position](
            self, value: T, info: FieldSerializationInfo
    ) -> T | str | dict[str, str] | None:
        if not info.by_alias:  # not serializing to tag IDs
            return value
        if not isinstance(value, Position):
            return

        field: FieldInfo = self.__class__.model_fields[info.field_name]
        if not isinstance(field.validation_alias, AliasChoices):
            return str(value)

        aliases = [al for al in field.validation_alias.choices if isinstance(al, str)]
        data = dict(zip(aliases, (value.number, value.total)))
        return {k: str(v).zfill(value.zero_fill) for k, v in data.items() if v is not None}

    @staticmethod
    def _flatten_dump(data: MutableMapping[str, Any]) -> None:
        for key, val in copy(data).items():
            if isinstance(val, Mapping):
                data |= data.pop(key)

    @staticmethod
    def _convert_values_to_list(data: MutableMapping[str, Any]) -> None:
        for key, val in data.items():
            if not isinstance(val, (tuple, list)):
                data[key] = [val]

    def _extend_with_uris(self, values: MutableSequence[Any], info: FieldSerializationInfo) -> None:
        context = info.context
        if self.uris and isinstance(context, TagDumpContext) and context.map_uri_to_tag == info.field_name:
            values.extend(self.uris)

    # noinspection PyNestedDecorators
    @field_validator("images", mode="before")
    @classmethod
    def _map_images[T](cls, images: Iterable) -> T | dict[str, ImageSource]:
        if not isinstance(images, tuple | list):
            return images

        mapped_images: dict[str, ImageSource] = {}
        for image in images:
            if isinstance(image, ImageSource):
                key = image.type
            else:
                key = cls.EmbeddedImage.get_id3_type_from_tag(image)

            if key is None:
                key = "COVER_FRONT"
            if key not in mapped_images:
                mapped_images[key] = image

        return mapped_images

    @field_serializer("images", mode="plain", when_used="unless-none")
    def _serialize_images(self, images: Any, info: FieldSerializationInfo) -> list:
        if not info.by_alias or not self.images:  # if not serializing to tag IDs, return the images models
            return images

        context = info.context
        if not isinstance(context, TagDumpContext) or not context.loaded_images:
            return []
        if missing_images := set(context.loaded_images) - set(self.images or ()):
            # noinspection PyUnboundLocalVariable
            raise FileError(f"Some image types are missing from the loaded images: {", ".join(missing_images)}")

        return [
            self.EmbeddedImage.from_image_model(model).build(context.loaded_images[kind])
            for kind, model in self.images.items()
        ]

    ###########################################################################
    ## IO
    ###########################################################################
    @classmethod
    def _check_tag_fields(cls, include: Collection[str], exclude: Collection[str]) -> None:
        if extra_fields := (set(include) | set(exclude)) - set(cls.__tag_fields__):
            raise TagError(f"Unrecognised tag fields: {', '.join(extra_fields)}")

    async def _check_and_load_file(self, file: FT = None) -> FT:
        if file is None:
            file = await self.load_file(self.path)
        return file

    async def load(self, file: FT = None) -> FT:
        file = await self._check_and_load_file(file=file)
        model = self.model_validate(file)
        self.__dict__ = model.__dict__
        return file

    async def save(self, file: FT) -> FT:
        # TODO: make this async somehow?
        file.save()
        return file

    @classmethod
    def clear(
            cls,
            file: FT,
            include: Collection[str] = (),
            exclude: Collection[str] = (),
    ) -> dict[str, set[str]]:
        cls._check_tag_fields(include=include, exclude=exclude)

        names = (set(include or cls.__tag_fields__) - set(exclude)) & cls.__tag_fields__
        removed = {
            name: {tag_id for alias in cls._get_aliases(name) for tag_id in cls._clear_tag(file, alias)}
            for name in names
        }
        return {k: v for k, v in removed.items() if v}

    @staticmethod
    def _clear_tag(file: FT, tag_id: str) -> set[str]:
        removed = set()
        if tag_id in file.tags:
            # noinspection PyTypeHints
            del file.tags[tag_id]
            removed.add(tag_id)
        return removed

    def update(
            self,
            file: FT,
            include: Collection[str] = (),
            exclude: Collection[str] = (),
            context: TagDumpContext = None,
            replace: bool = False,
    ) -> dict[str, Any]:
        """
        Update the tags of the given file with the data from this model.

        :param file: The file to update the tags of.
        :param include: The tags to include. If empty, all tags will be included.
        :param exclude: The tags to exclude. Ignored if empty.
        :param context: The context to use when dumping the tags.
        :param replace: Whether to replace existing tags with the same ID. If False, existing tags will be preserved.
        :return: The tags that were updated on the file.
        """
        self._check_tag_fields(include=include, exclude=exclude)

        tags = self.to_tags(include=include, exclude=exclude, context=context)
        if not replace:
            tags = {k: v for k, v in tags.items() if k not in file.tags}

        file.update(tags)
        return tags

    def to_tags(
            self,
            include: Collection[str] = (),
            exclude: Collection[str] = (),
            context: TagDumpContext[FT] = None
    ) -> dict[str, Any]:
        include = set(include or self.__tag_fields__) & set(self.__tag_fields__)
        exclude = set(exclude) & set(self.__tag_fields__)

        return self.model_dump(
            include=include,
            exclude=exclude,
            context=context,
            by_alias=True,
            exclude_none=True,
            exclude_defaults=True,
            exclude_unset=True,
        )

    def merge(
            self,
            other: Track,
            include: Collection[str] = (),
            exclude: Collection[str] = (),
            replace: bool = False,
    ) -> dict[str, Any]:
        """
        Merge the data from another track into this track.

        :param other: The track to merge data from.
        :param include: The fields to include in the merge. If empty, all fields will be included.
        :param exclude: The fields to exclude from the merge. Ignored if empty.
        :param replace: Whether to replace the existing value of a field if it is not None.
        :return: The fields that were updated on this track.
        """
        include = set(include or self.__tag_fields__) & set(self.__tag_fields__)
        exclude = set(exclude) & set(self.__tag_fields__)

        updated = {}
        for field in include - exclude:
            if not hasattr(other, field):
                continue

            value = getattr(other, field)
            if value == getattr(self, field):
                continue
            if not replace and getattr(self, field) is not None:
                continue

            setattr(self, field, value)
            updated[field] = value

        return updated


class HasLocalTracks[TK, TV: LocalTrack](HasMutableTracks[TK, TV], HasLogger):
    @validate_call
    async def save_tracks(
            self,
            include: Sequence[str] = (),
            exclude: Sequence[str] = (),
            context: TagDumpContext | None = None,
            replace: bool = False,
            dry_run: bool = True
    ) -> dict[Path, dict[str, Any]]:
        """
        Save tags for all tracks in this collection.

        :param include: The tags to include when writing to the file. If empty, all tags will be included.
        :param exclude: The tags to exclude from writing to the file. Ignored if empty.
        :param context: The context to use when writing the tags.
        :param replace: Destructively replace tags in each file.
        :param dry_run: Run function, but do not modify the file on the disk.
        :return: A map of the track path to the tags that were saved.
        """
        async def _save_track(track: LocalTrack) -> tuple[Path, dict[str, Any]]:
            file = await track.load()
            tags = track.update(file, include=include, exclude=exclude, context=context, replace=replace)
            if tags and not dry_run:
                await track.save(file)

            return track.path, tags

        self._log_save_tracks_header()

        # WARNING: making this run asynchronously will break tqdm; bar will get stuck after 1-2 ticks
        bar = self.logger.get_asynchronous_iterator(
            map(_save_track, self.tracks),
            desc="Updating tracks",
            unit="tracks",
            initial=0,
            total=len(self.tracks)
        )
        return dict(await bar)

    def _log_save_tracks_header(self) -> None:
        message = f"Saving {len(self.tracks)} tracks"

        if isinstance(self.type, str):
            message += f" in {self.type}"

        match self:
            case HasName() as named:
                message += f": {named.name!r}"
            case Library() as library if isinstance(library.source, str):
                message += f": {library.source!r}"

        self.logger.info(message, header=2)

    def log_save_tracks_results(self, results: dict[Path, dict[str, Any]]) -> None:
        """Log the results of saving tracks."""
        for path, tags in results.items():
            if tags:
                self.logger.info(f"Updated {path.name} with tags: {', '.join(tags)}")
            else:
                self.logger.info(f"No tags updated for {path.name}")

    @validate_call
    def merge_tracks(
            self,
            others: Iterable[Track],
            include: Sequence[str] = (),
            exclude: Sequence[str] = (),
            replace: bool = False,
    ) -> dict[Path, dict[str, Any]]:
        """
        Merge the given tracks into the tracks of this collection.

        :param others: The tracks to merge into this collection.
        :param include: The fields to include in the merge. If empty, all fields will be included.
        :param exclude: The fields to exclude from the merge. Ignored if empty.
        :param replace: Whether to replace the existing value of a field if it is not None.
        :return: A map of the track path to the fields that were updated on that track.
        """
        updated: dict[Path, dict[str, Any]] = {}
        for other in others:
            track = self.tracks.get(other)
            if track is None:
                continue

            result = track.merge(other, include=include, exclude=exclude, replace=replace)
            if result:
                updated[track.path] = result

        return updated
