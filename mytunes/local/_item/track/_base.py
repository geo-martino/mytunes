import itertools
from abc import abstractmethod
from collections.abc import Collection, Mapping, MutableMapping, MutableSequence, Iterable, Sequence
from contextlib import suppress
from copy import copy
from functools import cached_property
from io import BytesIO
from logging import DEBUG
from pathlib import Path
from typing import Self, Any, Literal, ClassVar, Annotated

import mutagen
import mutagen.id3
from PIL import Image, ImageFile as PILImageFile
from mutagen import FileType
from pydantic import field_validator, model_validator, validate_call, AliasChoices, ModelWrapValidatorHandler, \
    field_serializer, BeforeValidator, TypeAdapter, ValidationError
# noinspection PyProtectedMember
from pydantic.fields import Field, FieldInfo, ComputedFieldInfo
from pydantic_core.core_schema import FieldSerializationInfo, ValidationInfo, SerializerFunctionWrapHandler

from mytunes._types import StrippedString, to_list
from mytunes.core.library import Library
from mytunes.core.properties.asynch import SemaphoreT
from mytunes.core.properties.audio import HasAudioProperties
from mytunes.core.properties.date import HasAddedDate, HasPlayedDate
from mytunes.core.properties.file import IsReadableFile, IsWriteableFile, IsLocalFile
from mytunes.core.properties.image import FileEmbeddedImage, ImageSource, PILImageFileT
from mytunes.core.properties.logger import HasLogger, HasProgress
from mytunes.core.properties.name import HasName
from mytunes.core.properties.order import Position
from mytunes.core.properties.uri import HasMutableURI, URI
from mytunes.core.track import Track, HasMutableTracks
from mytunes.exception import MyTunesTypeError, MyTunesValueError
from mytunes.local._base import LocalModel
from mytunes.local._item.album import LocalAlbum
from mytunes.local._item.artist import LocalArtist
from mytunes.local._item.genre import LocalGenre
from mytunes.local._item.track._types import ItemSequence
from mytunes.local.exception import FileError
from ...._base import BaseModel, makecls
from ...._base.attribute import TagAttribute
from ...._base.resource import ResourceModel


class TagContext(BaseModel):
    remote_source: StrippedString | None = Field(
        description="The remote source for determining which URI to use when processing track URIs.",
        default=None,
        validation_alias="source",
    )
    map_uri_to_field: Literal["comments"] = Field(
        description="The field to use for storing the URIs of the track.",
        default="comments",
        validation_alias=AliasChoices("field", "tag"),
    )
    loaded_images: Mapping[str, PILImageFileT] = Field(
        description="The image properties and their loaded images.",
        default_factory=dict,
        validation_alias="images",
    )


# noinspection PyAbstractClass
class LocalAudioFile(IsReadableFile, IsWriteableFile, IsLocalFile, HasAudioProperties):
    @classmethod
    def _extract_tags_from_mutagen(cls, file: mutagen.FileType) -> dict[str, Any]:
        data = IsLocalFile._extract_tags_from_mutagen(file)
        data |= HasAudioProperties._extract_tags_from_mutagen(file)
        return data


# noinspection PyAbstractClass
class LocalTrack[FT: FileType](
    LocalModel,
    LocalAudioFile,
    HasMutableURI,
    HasAddedDate,
    HasPlayedDate,
    Track[LocalArtist, LocalAlbum, LocalGenre],
    metaclass=makecls(),
):
    __supported_types__: ClassVar[Sequence[type[mutagen.FileType]] | None] = None

    # override to apply file tag metadata and alias
    name: Annotated[StrippedString, TagAttribute()] = Field(
        description="The name of this track.",
        alias="title",
    )
    # override to apply file tag metadata
    album: Annotated[LocalAlbum | None, TagAttribute()] = Field(
        description="The album this track is featured on.",
        default=None,
    )

    @cached_property
    def _uri_adapter(self) -> TypeAdapter[URI]:
        return TypeAdapter(URI.annotation)

    @model_validator(mode="wrap")
    @classmethod
    def _set_computed_fields(cls, data: Any, handler: ModelWrapValidatorHandler[Self]) -> Self:
        model: Self = handler(data)

        for field_name in cls.model_computed_fields:
            if field_name not in cls.__tag_attributes__ or not hasattr(getattr(cls, field_name), "fset"):
                continue
            if (value := cls._get_value_from_data(data, field_name)) is None:
                continue
            if value == getattr(model, field_name):
                continue
            setattr(model, field_name, value)

        return model

    # noinspection PyAbstractClass
    class EmbeddedImage[TT](FileEmbeddedImage):
        alias: ClassVar[str | AliasChoices] = "images"

        @model_validator(mode="wrap")
        @classmethod
        def _from_tag_value(cls, value: TT, handler: ModelWrapValidatorHandler[Self]) -> Self:
            img_bytes = cls._get_bytes(value)
            if not isinstance(img_bytes, bytes):
                return handler(value)

            img = Image.open(BytesIO(img_bytes))
            obj = handler(img)
            del img  # ensure memory is recovered, could probably delete this?

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
                    raise FileError(self.path, "Given file does not match the path of this image.")
                return file

            if self.path is None:
                raise FileError(message="Path is not set and no loaded file was given, cannot load image.")
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

    @Track.album_artist.setter
    def album_artist(self, value: Any) -> None:
        value = to_list(value)
        for val in reversed(value):
            super(Track, type(self)).album_artist.fset(self, val)

    @Track.compilation.setter
    def compilation(self, value: Any) -> None:
        value = self._extract_first_value_from_single_sequence(value)
        super(Track, type(self)).compilation.fset(self, value)

    ###########################################################################
    ## Utility Methods
    ###########################################################################
    @classmethod
    @validate_call
    async def from_path(cls, path: str | Path) -> Self:
        file = await cls.load_file(path)
        # some subclasses need to access the file obj on construction so just pass the file obj
        return cls.model_validate(file)

    @classmethod
    @validate_call
    async def load_file(cls, path: str | Path) -> FT:
        # TODO: improve async performance here
        #  Synchronous loads through mutagen are much faster than async loads,
        #  possibly because mutagen only loads the header and not the whole audio file.
        #  Can we implement an async load for just the file header?

        # async with aiofiles.open(path, mode='rb') as file:
        #     try:
        #         file = mutagen.File(BytesIO(await file.read()), options=cls.__supported_types__)
        #     except MutagenError:  # async load doesn't always work...
        #         # fallback to loading synchronously directly through mutagen
        #         file = mutagen.File(path, options=cls.__supported_types__)

        file = mutagen.File(path, options=cls.__supported_types__)
        if file is None:
            raise FileError(path=path, message="Failed to load file to the expected type")

        file.filename = str(path)  # this is needed when loading from bytes as path is not passed to mutagen
        return file

    @classmethod
    def _get_tag_id(cls, name: str) -> str | None:
        tag_id = name
        match cls.model_fields.get(name, cls.model_computed_fields.get(name)):
            case FieldInfo() as field if isinstance(field.serialization_alias, str):
                tag_id = field.serialization_alias
            case FieldInfo() | ComputedFieldInfo() as field if isinstance(field.alias, str):
                tag_id = field.alias
            case FieldInfo() as field if isinstance(field.validation_alias, str):
                tag_id = field.validation_alias
            case FieldInfo() as field if isinstance(field.validation_alias, AliasChoices):
                tag_id = next(iter(field.validation_alias.choices))

        return tag_id

    @classmethod
    def _get_ext_from_input(cls, value: Any) -> str:
        if isinstance(value, mutagen.FileType):
            value = Path(value.filename)
        return super()._get_ext_from_input(value)

    ###########################################################################
    ## Validators/Serializers
    ###########################################################################
    @classmethod
    def _extract_tags_from_mutagen(cls, file: mutagen.FileType) -> dict[str, Any]:
        """Extract tags from a mutagen file object."""
        return dict(file.tags) | super()._extract_tags_from_mutagen(file)

    @field_validator(
        "name", "album", "bpm", "key", "uri", "rating",
        mode="before", check_fields=True
    )
    @staticmethod
    def _extract_first_value_from_sequence[T](value: Sequence[T]) -> T:
        if isinstance(value, ItemSequence) and len(value) >= 1:
            value = value[0]
        return value

    @field_validator(
        "name", "album", "track", "disc", "bpm", "key", "released_at", "uri",
        mode="before", check_fields=True
    )
    @staticmethod
    def _extract_first_value_from_single_sequence[T](value: Sequence[T]) -> T:
        if isinstance(value, ItemSequence) and len(value) == 1:
            value = value[0]
        return value

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

    @field_validator(
        "genres", "comments",
        mode="before", check_fields=True
    )
    @classmethod
    def _split_joined_tags[T: str](cls, value: T) -> T | list[str]:
        if not isinstance(value, ItemSequence) or not all(isinstance(v, str) for v in value):
            return value
        return list(itertools.chain.from_iterable(map(cls._separate_tags, value)))

    def _join_split_tags(self, value: Iterable[Any]) -> str:
        # noinspection PyTypeChecker
        values = (self._serialize_name(val, lambda x: x, None) for val in value)
        return self._join_tags(str(v) for v in values if v and str(v))

    @field_serializer("album", "album_artist", mode="wrap", when_used="unless-none")
    def _serialize_name(
            self,
            value: str | HasName,
            handler: SerializerFunctionWrapHandler,
            info: FieldSerializationInfo,
    ) -> str | None:
        if not isinstance(value, HasName):
            return handler(value)
        return value.name if value is not None else None

    @field_serializer("artists", mode="wrap", when_used="unless-none")
    def _serialize_names(
            self,
            values: Iterable[str | HasName],
            handler: SerializerFunctionWrapHandler,
            info: FieldSerializationInfo,
    ) -> str | list[str] | dict[str, str]:
        if info and info.mode != "json":
            return self._join_split_tags(values)

        if not isinstance(values, Iterable):
            return handler(values)

        values = [self._serialize_name(value, handler=handler, info=info) for value in values]
        return values

    @staticmethod
    def _serialize_position_tags(value: Position, field: FieldInfo) -> str | dict[str, str]:
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
            if isinstance(val, bool):  # never convert bools to list of bools
                continue
            if not isinstance(val, ItemSequence):
                data[key] = [val]

    @model_validator(mode="after")
    def _assign_uris_from_context(self, info: ValidationInfo) -> Self:
        if not isinstance(context := info.context, TagContext):
            return self
        if context.remote_source and context.remote_source.casefold() != (self.source or "").casefold():
            self.source = context.remote_source

        if not (values := getattr(self, context.map_uri_to_field, [])):
            return self

        uris = []
        for value in values:
            with suppress(ValidationError):
                uri = self._uri_adapter.validate_python(value)
                uris.append(uri)

        if values != self.uris:
            self.__dict__["uris"] = set(uris)
        return self

    def _extend_with_uris(self, values: MutableSequence[Any], info: FieldSerializationInfo) -> None:
        context = info.context
        if self.uris and isinstance(context, TagContext) and context.map_uri_to_field == info.field_name:
            values.extend(self.uris)

    @field_validator("images", mode="before")
    @classmethod
    def _map_images[T](cls, images: Iterable) -> T | dict[str, ImageSource]:
        if not isinstance(images, ItemSequence):
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

    @model_validator(mode="after")
    def _assign_path_to_embedded_images(self) -> Self:
        for image in self.images.values():
            if isinstance(image, self.EmbeddedImage) and image.path is None:
                image.path = self.path

        return self

    @field_serializer("images", mode="plain", when_used="unless-none")
    def _serialize_images[T](self, images: dict[str, Any], info: FieldSerializationInfo) -> list | T:
        if not info.by_alias or not self.images:  # if not serializing to tag IDs, return the images models
            return images

        context = info.context
        if not isinstance(context, TagContext) or not context.loaded_images:
            return []
        if missing_images := set(context.loaded_images) - set(self.images or ()):
            # noinspection PyUnboundLocalVariable
            raise FileError(
                self.path,
                f"Some image types are missing from the loaded images: {", ".join(missing_images)}"
            )

        return [
            self.EmbeddedImage.from_image_model(model).build(context.loaded_images[kind])
            for kind, model in self.images.items()
        ]

    ###########################################################################
    ## IO
    ###########################################################################
    @classmethod
    def _validate_tag_fields(cls, fields: Collection[str]) -> tuple[str, ...]:
        invalid_tag_fields = [field for field in fields if field not in cls.__tag_fields__]
        if invalid_tag_fields:
            raise MyTunesValueError(f"Unrecognised tag fields: {", ".join(invalid_tag_fields)}")
        return tuple(fields)

    @classmethod
    def _map_uri_field(cls, fields: Collection[str], context: TagContext = None) -> tuple[str, ...]:
        fields = list(fields)
        if context is not None and context.map_uri_to_field and "uri" in fields:
            fields.remove("uri")
            fields.append(context.map_uri_to_field)

        return tuple(fields)

    @classmethod
    def _map_tag_fields(cls, fields: Collection[str]) -> tuple[str, ...]:
        fields = cls._map_uri_field(fields)

        tag_fields = []
        for field in cls._validate_tag_fields(fields):
            if (tag_field := cls.__tag_fields__[field]) not in tag_fields:
                tag_fields.append(tag_field)

        return tuple(tag_fields)

    async def _check_and_load_file(self, file: FT = None) -> FT:
        if file is None:
            file = await self.load_file(self.path)
        return file

    async def load(self, file: FT = None) -> FT:
        file = await self._check_and_load_file(file=file)
        model = self.model_validate(file)
        self.__dict__ = model.__dict__
        return file

    async def save(self, dry_run: bool = False, file: FT = None) -> FT:
        if dry_run or file is None:
            return file

        # TODO: make this async somehow?
        file.save()
        return file

    @classmethod
    def clear(
            cls,
            file: FT,
            include: Collection[str] = (),
            exclude: Collection[str] = (),
            context: TagContext = None,
    ) -> dict[str, set[str]]:
        include = cls._map_uri_field(include, context=context)
        include = cls._validate_tag_fields(include or cls.__tag_fields__)

        exclude = cls._map_uri_field(exclude, context=context)
        exclude = cls._validate_tag_fields(exclude)

        tag_fields = set(include) - set(exclude)
        removed = {
            tag_field: {
                tag_id for alias in cls._get_aliases(tag_field, with_serialization_alias=True)
                for tag_id in cls._clear_tag(file, alias)
            }
            for tag_field in tag_fields
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
            context: TagContext = None,
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
        tags = self.to_tags(include=include, exclude=exclude, context=context)
        tags = self._drop_matching_tags(file, tags)
        if not replace:
            tags = self._drop_existing_tags(file, tags)

        if tags:
            file.update(tags)
        return tags

    @staticmethod
    def _drop_matching_tags(file: FT, tags: Mapping[str, Any]) -> dict[str, Any]:
        clean: dict[str, Any] = {}
        for key, value in tags.items():
            if key not in file:
                clean[key] = value

            existing = file.tags.get(key)
            if value == existing:
                continue

            clean[key] = value

        return clean

    @staticmethod
    def _drop_existing_tags(file: FT, tags: Mapping[str, Any]) -> dict[str, Any]:
        return {k: v for k, v in tags.items() if k not in file.tags}

    def to_tags(
            self,
            include: Collection[str] = (),
            exclude: Collection[str] = (),
            context: TagContext[FT] = None
    ) -> dict[str, Any]:
        include = self._map_uri_field(include, context=context)
        include = self._validate_tag_fields(include or self.__tag_fields__)

        exclude = self._map_uri_field(exclude, context=context)
        exclude = self._validate_tag_fields(exclude)

        return self.model_dump(
            include=set(include),
            exclude=set(exclude),
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
        include = self._map_tag_fields(include or self.__tag_fields__)
        exclude = self._map_tag_fields(exclude)
        tag_fields = set(include) - set(exclude)

        updated = {}
        for tag_field in tag_fields:
            if not hasattr(other, tag_field):
                continue
            if "." in tag_field and ".".join(tag_field.split(".")[:-1]) in tag_fields:
                continue  # skip if already setting parent

            value = getattr(other, tag_field)
            if value == getattr(self, tag_field):
                continue
            if not replace and getattr(self, tag_field) is not None:
                continue

            setattr(self, tag_field, value)
            updated[tag_field] = value

        return updated


class HasLocalTracks[TT: LocalTrack](HasMutableTracks[TT], HasLogger, HasProgress):
    concurrency: SemaphoreT = Field(
        description=(
            "The max concurrency of IO tasks (i.e. loading/saving) of files in this library. "
            "Setting this too low will reduce the speed of these operations. "
            "Setting this too high will cause these operations to hang."
        ),
        default=32,
        repr=False,
    )

    @validate_call
    async def save_tracks(
            self,
            include: set[str] | Sequence[str] = (),
            exclude: set[str] | Sequence[str] = (),
            context: TagContext | None = None,
            replace: bool = False,
            dry_run: bool = False
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
            async with self.concurrency:
                file = await track.load_file(track.path)
                tags = track.update(file, include=include, exclude=exclude, context=context, replace=replace)
                if tags:
                    await track.save(dry_run=dry_run, file=file)

            return track.path, tags

        self._log_save_tracks_header()

        task_id = self._progress.add_task(description=f"Updating local tracks", total=len(self.tracks))
        results = await self._run_tasks_async(map(_save_track, self.tracks), task_id=task_id)
        return dict(results)

    def _log_save_tracks_header(self) -> None:
        message = f"Saving {len(self.tracks)} tracks"

        match self:
            case Library() as lib:
                message += f" in {lib.source} {lib.type}"
            case ResourceModel() as resource if isinstance(resource.type, str):
                message += f" in {resource.type}"

        if isinstance(self, HasName):
            message += f": {self.name!r}"

        self._logger.info(message, header=2)

    @validate_call
    def log_save_tracks_results(self, results: Mapping[Path, Iterable[str]], dry_run: bool = False) -> None:
        """Log the given results of saving tracks."""
        self._logger.print_line(DEBUG)

        for path, tags in results.items():
            if tags and dry_run:
                self._logger.debug(f"Would have updated {path.name} with tags: {', '.join(tags)}")
            elif tags:
                self._logger.debug(f"Updated {path.name} with tags: {', '.join(tags)}")
            else:
                self._logger.debug(f"No tags updated for {path.name}")

    @validate_call
    def merge_tracks(
            self,
            others: Iterable[Track],
            include: set[str] | Sequence[str] = (),
            exclude: set[str] | Sequence[str] = (),
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
            if track is None and isinstance(other, LocalTrack):
                track = next((it for it in self.tracks if it.path == other.path), None)
            if track is None:
                continue

            result = track.merge(other, include=include, exclude=exclude, replace=replace)
            if result:
                updated[track.path] = result

        return updated

    ###########################################################################
    ## Restore
    ###########################################################################
    @staticmethod
    def _extract_tracks_from_backup(backup: Any) -> list[LocalTrack]:
        if isinstance(backup, Mapping) and "tracks" in backup:
            backup = backup["tracks"]

        match backup:
            case Mapping() as items if all(isinstance(item, Mapping) for item in items.values()):
                tracks = items.values()
            case Collection() as items if all(isinstance(item, Mapping) for item in items):
                tracks = items
            case _:
                raise MyTunesTypeError(f"Unrecognised backup dump format: {type(backup).__name__!r}.")

        for track in tracks:  # drop uris as they cause validation errors and are not needed for restoration
            track.pop("uri", None)
            track.pop("uris", None)

        adapter = TypeAdapter[LocalTrack](LocalTrack.annotation)
        return list(map(adapter.validate_python, tracks))

    @validate_call
    def restore_tracks(
            self,
            others: Annotated[Sequence[LocalTrack], BeforeValidator(_extract_tracks_from_backup)],
            include: set[str] | Sequence[str] = (),
            exclude: set[str] | Sequence[str] = (),
    ) -> dict[Path, dict[str, Any]]:
        """
        Restore track tags from a backup to loaded track objects. This does not save the updated tags.

        Backup may be in the form of either:
            * An iterable of dictionaries where dictionary is ``{<Dump of track data>}``
            * A mapping of ``{<path>: {<Dump of track data>}}``
            * A mapping of ``{"tracks": {<path>: {<Dump of track data>}}}``
            * An iterable of track objects

        :param others: Backup data. See description for accepted formats.
        :param include: The fields to include in the merge. If empty, all fields will be included.
        :param exclude: The fields to exclude from the merge. Ignored if empty.
        :return: A map of the track path to the fields that were updated on that track.
        """
        return self.merge_tracks(others=others, include=include, exclude=exclude, replace=True)
