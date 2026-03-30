"""
The XAutoPF implementation of a :py:class:`LocalPlaylist`.
"""
from __future__ import annotations

from abc import ABCMeta, abstractmethod
from collections.abc import Collection, Mapping, MutableMapping, MutableSequence
from copy import deepcopy
from pathlib import Path
from random import choice
from typing import Any, Self, Literal, Annotated, ClassVar, get_origin, final

from pydantic import Field, field_validator, model_validator, ConfigDict, BeforeValidator, model_serializer, \
    field_serializer, TypeAdapter, NonNegativeInt, PositiveInt, ModelWrapValidatorHandler, AliasChoices
from pydantic.alias_generators import to_pascal, to_snake
from pydantic.fields import FieldInfo, PrivateAttr
from pydantic_core.core_schema import SerializationInfo, SerializerFunctionWrapHandler
from typing_inspection.typing_objects import is_annotated

from musify._types import StrippedString, to_list
from musify.exception import MusifyValueError
from musify.local.collection.playlist import LocalPlaylist
from musify.local.item.track import LocalTrack
from musify.models import BaseModel
from musify.models.exception import MusifyValidationError
from musify.models.result import LogFormatter, CountResult
from musify.models.sequence import MutableUniqueSequence
from musify.processors.compare import Comparer
from musify.processors.filters import MatchFilter, PathsFilter, ComparerFilter, MatchResult
from musify.processors.limit import ItemLimiter
from musify.processors.sort import ItemSorter

try:
    import xmltodict
except ImportError:
    xmltodict = None

AutoMatcher = MatchFilter[LocalTrack, PathsFilter, PathsFilter]


@final
class SyncXAutoPFResult(CountResult):
    """Stores the results of a sync with a local XAutoPF playlist."""
    __final__ = True
    __required_modules__ = {"xmltodict": xmltodict}

    start: Annotated[
        NonNegativeInt,
        LogFormatter(width=6, alignment="right", colour="blue", colour_attributes=["bold"]),
    ] = Field(
        description="The total number of tracks in the playlist before the sync."
    )
    start_included: Annotated[
        NonNegativeInt,
        LogFormatter(width=6, alignment="right", colour="green", colour_attributes=["bold"]),
    ] = Field(
        description="The number of tracks that matched the include settings before the sync."
    )
    start_excluded: Annotated[
        NonNegativeInt,
        LogFormatter(width=6, alignment="right", colour="red", colour_attributes=["bold"]),
    ] = Field(
        description="The number of tracks that matched the exclude settings before the sync."
    )
    start_compared: Annotated[
        NonNegativeInt,
        LogFormatter(width=6, alignment="right", colour="yellow", colour_attributes=["bold"]),
    ] = Field(
        description="The number of tracks that matched the comparer settings before the sync."
    )
    start_limit: Annotated[
        NonNegativeInt,
        LogFormatter(width=6, alignment="right", colour="magenta", colour_attributes=["bold"]),
    ] = Field(
        description="The limit count before the sync. 0 if no limiter was present."
    )
    start_sort: Annotated[
        bool,
        LogFormatter(width=6, alignment="right", colour="magenta", colour_attributes=["bold"]),
    ] = Field(
        description="Was a sorter present on the playlist before the sync."
    )

    final: Annotated[
        NonNegativeInt,
        LogFormatter(width=6, alignment="right", colour="blue", colour_attributes=["bold"]),
    ] = Field(
        description="The total number of tracks in the playlist after the sync."
    )
    final_included: Annotated[
        NonNegativeInt,
        LogFormatter(width=6, alignment="right", colour="green", colour_attributes=["bold"]),
    ] = Field(
        description="The number of tracks that matched the include settings after the sync."
    )
    final_excluded: Annotated[
        NonNegativeInt,
        LogFormatter(width=6, alignment="right", colour="red", colour_attributes=["bold"]),
    ] = Field(
        description="The number of tracks that matched the exclude settings after the sync."
    )
    final_compared: Annotated[
        NonNegativeInt,
        LogFormatter(width=6, alignment="right", colour="yellow", colour_attributes=["bold"]),
    ] = Field(
        description="The number of tracks that matched the comparer settings after the sync."
    )
    final_limit: Annotated[
        NonNegativeInt,
        LogFormatter(width=6, alignment="right", colour="magenta", colour_attributes=["bold"]),
    ] = Field(
        description="The limit count after the sync. 0 if no limiter was present."
    )
    final_sort: Annotated[
        bool,
        LogFormatter(width=6, alignment="right", colour="magenta", colour_attributes=["bold"]),
    ] = Field(
        description="Was a sorter present on the playlist after the sync."
    )

    @classmethod
    def from_xml(
            cls,
            initial_tracks: MutableSequence[LocalTrack],
            initial_xml: _XMLRoot,
            final_tracks: MutableSequence[LocalTrack],
            final_xml: _XMLRoot,
            reference: LocalTrack | None = None,
    ) -> Self:
        """Create a sync result from the given XML objects."""
        return cls(
            start=len(initial_tracks),
            start_included=len(initial_xml.smart_playlist.source.exceptions_include or ()),
            start_excluded=len(initial_xml.smart_playlist.source.exceptions or ()),
            start_compared=len(
                initial_xml.smart_playlist.source.conditions.comparers.apply(initial_tracks, reference=reference)
            ),
            start_limit=(
                initial_xml.smart_playlist.source.limit.count
                if initial_xml.smart_playlist.source.limit.enabled else 0
            ),
            start_sort=(
                len(initial_xml.smart_playlist.source.sort_by.sort_fields) > 0
                if initial_xml.smart_playlist.source.sort_by is not None else False
            ),
            final=len(final_tracks),
            final_included=len(final_xml.smart_playlist.source.exceptions_include or ()),
            final_excluded=len(final_xml.smart_playlist.source.exceptions or ()),
            final_compared=len(
                final_xml.smart_playlist.source.conditions.comparers.apply(final_tracks, reference=reference)
            ),
            final_limit=(
                final_xml.smart_playlist.source.limit.count
                if final_xml.smart_playlist.source.limit.enabled else 0
            ),
            final_sort=(
                len(final_xml.smart_playlist.source.sort_by.sort_fields) > 0
                if final_xml.smart_playlist.source.sort_by is not None else False
            ),
        )


@final
class XAutoPF(LocalPlaylist[AutoMatcher]):
    """For reading and writing data from MusicBee's auto-playlist format."""
    __final__ = True
    __required_modules__ = {"xmltodict": xmltodict}
    __supported_extensions__ = frozenset({"xautopf"})

    _xml: _XMLRoot | None = PrivateAttr(default=None)
    _original: MutableUniqueSequence = PrivateAttr(default_factory=MutableUniqueSequence)

    @property
    def limiter_deduplication(self) -> bool:
        """Controls whether duplicates should be filtered out before running limiter operations."""
        return self._xml.smart_playlist.source.limit.filter_duplicates

    @limiter_deduplication.setter
    def limiter_deduplication(self, value: bool):
        self._xml.smart_playlist.source.limit.filter_duplicates = value

    @staticmethod
    def _get_reference_for_last_played_track(tracks: MutableSequence[LocalTrack]) -> LocalTrack | None:
        try:
            ItemSorter.sort_by_field(tracks, field="last_played_at", reverse=True)
            return tracks[0]
        except MusifyValueError:
            return

    async def load(self, tracks: Collection[LocalTrack] = ()) -> Self:
        """
        Read the playlist file and update the tracks in this playlist instance.

        :param tracks: Available Tracks to search through for matches.
            If no tracks are given, the playlist will be loaded empty.
        :return: Self
        """
        if self.path.is_file():
            with self.path.open("r") as file:
                self._xml = _XMLRoot.model_validate(file.read())
        elif self._xml is None:  # this is a new playlist, assign default values
            self._xml = _XMLRoot()

        self.description = self._xml.smart_playlist.source.description

        matcher = self._xml.smart_playlist.matcher
        matcher.include.path_mapper = self.path_mapper
        matcher.exclude.path_mapper = self.path_mapper

        self.matcher = matcher
        self.limiter = self._xml.smart_playlist.source.limit.limiter
        self.sorter = self._xml.smart_playlist.sorter

        self._match_tracks(tracks=tracks, reference=self._get_reference_for_last_played_track(list(tracks)))
        self._limit_tracks(ignore=self.matcher.exclude.values)
        self._sort_tracks()

        self._original = self.tracks.copy()

        return self

    def _limit_tracks(self, ignore: Collection[Path]) -> None:
        if self.limiter is not None and self.tracks is not None and self.limiter_deduplication:
            self.tracks[:] = self.tracks.unique
        super()._limit_tracks(ignore=ignore)

    def log_load(self, result: MatchResult) -> None:
        """Log the given results of loading tracks."""
        table = MatchResult.generate_table(results={self.name: result})
        self.logger.stat(table)

    async def save(self, dry_run: bool = True, *_, **__) -> SyncXAutoPFResult:
        """
        Write the tracks in this Playlist and its settings (if applicable) to file.

        :param dry_run: Run function, but do not modify the file on the disk.
        :return: The results of the sync.
        """
        # TODO: make this async
        if self._xml is None:
            self._xml = _XMLRoot()

        initial_xml = deepcopy(self._xml)
        initial_tracks = self._original.copy()
        xml = self._xml if not dry_run else deepcopy(self._xml)

        xml.smart_playlist.source.description = self.description

        self._clean_matcher_paths()
        xml.smart_playlist.parse_matcher(self.matcher)
        xml.smart_playlist.source.limit.parse_limiter(self.limiter, filter_duplicates=self.limiter_deduplication)
        xml.smart_playlist.parse_sorter(self.sorter)

        if not dry_run:
            await self.rename()

            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(xml.unparse_xml(), encoding="utf-8")

            self._original = self.tracks.copy()

        reference = self._get_reference_for_last_played_track(initial_tracks + self.tracks)
        return SyncXAutoPFResult.from_xml(
            initial_xml=initial_xml,
            initial_tracks=initial_tracks,
            final_xml=xml,
            final_tracks=self.tracks,
            reference=reference,
        )

    def _clean_matcher_paths(self) -> None:
        """
        Ensures that the paths included in the XML output do not include paths that match
        any of the comparer or group_by conditions.

        Match original and current tracks again on current conditions to check for differences
        between compare, include and exclude settings.
        """
        if self.matcher is None or not self.matcher.ready:
            return

        track_paths = set(track.path for track in self.tracks)
        if not self.matcher.compare or not self.matcher.compare.ready:
            # no compare conditions so all tracks are included, none are excluded
            self.matcher.include.paths = track_paths
            self.matcher.exclude.paths = {}
            return

        tracks = self._original + self.tracks
        reference = self._get_reference_for_last_played_track(tracks)
        compared = {track.path for track in tracks if self.matcher.compare.check(track, reference=reference)}

        # noinspection PyTypeChecker
        included = compared | self.matcher.exclude.paths
        if self.matcher.include.path_mapper is not None:
            included = self.matcher.include.path_mapper.unmap_many(included, check_existence=False)
        self.matcher.include.values -= set(map(str, included))

        excluded = compared | self.matcher.include.paths
        if self.matcher.exclude.path_mapper is not None:
            excluded = self.matcher.exclude.path_mapper.unmap_many(excluded, check_existence=False)
        self.matcher.exclude.values &= set(map(str, excluded))

    def log_save(self, result: SyncXAutoPFResult) -> None:
        """Log the given results of matching tracks."""
        table = SyncXAutoPFResult.generate_table(results={self.name: result})
        self.logger.stat(table)


class _XMLField(metaclass=ABCMeta):
    @abstractmethod
    def get_field_key(self, key: str) -> str:
        """Format the given ``key`` according to the ``type`` of this field."""
        raise NotImplementedError


class _XMLElementField(_XMLField):
    def get_field_key(self, key: str) -> str:
        return key


class _XMLAttributeField(_XMLField):
    attr_prefix = "@"

    def get_field_key(self, key: str) -> str:
        return f"{self.attr_prefix}{key}"


class _XMLBaseModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=lambda name: to_pascal(name.lstrip("@#")),
    )

    @model_validator(mode="wrap")
    @classmethod
    def _clean_keys(cls, data: Mapping[str, Any], handler: ModelWrapValidatorHandler[Self]) -> Self:
        if not isinstance(data, Mapping):
            return handler(data)

        data = {key.lstrip("@#"): val for key, val in data.items()}
        return handler(data)

    def model_dump_xml(self) -> dict[str, Any]:
        """Dump the model to a dict suitable for XML serialization."""
        return self.model_dump(
            exclude_none=True,
            by_alias=True,
        )

    @model_serializer(mode="wrap")
    def _dump_xml(
            self, handler: SerializerFunctionWrapHandler, info: SerializationInfo
    ) -> dict[str, Any]:
        dump = handler(self)
        if not info.by_alias:
            return dump

        return self._serialize_xml(dump)

    @classmethod
    def _get_field_from_name(cls, name: str) -> FieldInfo:
        try:
            return cls.model_fields[to_snake(name)]
        except KeyError:
            return cls.model_fields[name]

    @classmethod
    def _get_xml_field_from_field(cls, field: FieldInfo) -> _XMLField | None:
        annotation = field.rebuild_annotation()
        if not is_annotated(get_origin(annotation)):
            return

        return next((meta for meta in annotation.__metadata__ if isinstance(meta, _XMLField)), None)

    @classmethod
    def _serialize_xml(cls, dump: dict[str, Any]) -> dict[str, Any]:
        order = list(dump.keys())
        for key, val in tuple(dump.items()):  # set attribute keys
            try:
                field: FieldInfo = cls._get_field_from_name(key)
            except KeyError:
                continue  # TODO: sometimes tries to dump the same model twice, why?

            if (xml_field := cls._get_xml_field_from_field(field)) is not None:
                dump[new_key := xml_field.get_field_key(key)] = dump.pop(key)
                order[order.index(key)] = new_key
                key = new_key

            if not isinstance(val, list) or not isinstance(xml_field, _XMLAttributeField):
                continue

            match len(val):
                case 0:
                    del dump[key]
                case 1:
                    dump[key] = val[0]
                case _:
                    for i, item in enumerate(val, 1):
                        new_key = f"{key}{i}"
                        dump[new_key] = item
                        if i == 0:
                            order[order.index(key) + i] = new_key
                        else:
                            order.insert(order.index(key) + i, new_key)
                    del dump[key]

        return dict(sorted(dump.items(), key=lambda it: order.index(it[0])))


class _XMLCondition(_XMLBaseModel):
    reference_values: ClassVar[set[Any]] = {"[playing track]"}

    # noinspection SpellCheckingInspection
    #: Map of MusicBee name to field name
    name_field_map: ClassVar[Mapping[str, str]] = {
        "None": None,
        "Title": "name",
        "ArtistPeople": "artist",
        "Album": "album",  # album ignoring articles like 'the' and 'a' etc.
        "Album Artist": "album.artist",
        "TrackNo": "track.number",
        "TrackCount": "track.total",
        "GenreSplits": "genres",
        "Year": "released_at.year",  # could also be 'YearOnly'?
        "BeatsPerMin": "bpm",
        "DiscNo": "disc.number",
        "DiscCount": "disc.total",
        # "": "compilation",  # unmapped for compare
        "Comment": "comments",
        "FileDuration": "length",
        "Rating": "rating",
        "Artwork": "images",
        # "ComposerPeople": "composer",  # currently not supported by this program
        # "Conductor": "conductor",  # currently not supported by this program
        # "Publisher": "publisher",  # currently not supported by this program
        "FilePath": "path",
        "FolderName": "folder",
        "FileName": "filename",
        "FileExtension": "ext",
        # "": "size",  # unmapped for compare
        "FileKind": "type",
        "FileBitrate": "bit_rate",
        "BitDepth": "bit_depth",
        "FileSampleRate": "sample_rate",
        "FileChannels": "channels",
        # "": "date_created",  # unmapped for compare
        "FileDateModified": "modified_at",
        "FileDateAdded": "added_at",
        "FileLastPlayed": "last_played_at",
        "FilePlayCount": "play_count",
    }
    #: Map of field name to MusicBee name
    field_name_map: ClassVar[Mapping[str, str]] = {field: name for name, field in name_field_map.items()}

    # noinspection SpellCheckingInspection
    #: Map of MusicBee name to field code
    name_code_map: ClassVar[Mapping[str, int]] = {
        "None": 0,
        "#": 78,
        "Title": 65,
        "ArtistPeople": 32,
        "Album": 30,  # album ignoring articles like 'the' and 'a' etc.
        "Album Artist": 31,
        "TrackNo": 86,
        "TrackCount": 87,
        "GenreSplits": 59,
        "Year": 35,  # could also be 'YearOnly'?
        "BeatsPerMin": 85,
        "DiscNo": 52,
        "DiscCount": 54,
        "DiscTrackNo": 53,
        # "": 904,  # unmapped for compare
        "Comment": 44,
        "FileDuration": 16,
        "Rating": 75,
        "Artwork": 40,
        # "ComposerPeople": 43,  # currently not supported by this program
        # "Conductor": 45,  # currently not supported by this program
        # "Publisher": 73,  # currently not supported by this program
        "FilePath": 106,
        "FolderName": 179,
        "FileName": 3,
        "FileExtension": 100,
        # "": 7,  # unmapped for compare
        "FileKind": 4,
        "FileBitrate": 10,
        "BitDepth": 183,
        "FileSampleRate": 9,
        "FileChannels": 8,
        # "": 921,  # unmapped for compare
        "FileDateModified": 11,
        "FileDateAdded": 12,
        "FileLastPlayed": 13,
        "FilePlayCount": 14,
        "FileDuplicateFlag": 20,
    }
    #: Map of field code to MusicBee name
    code_name_map: ClassVar[Mapping[int, str]] = {code: name for name, code in name_code_map.items()}

    field: Annotated[StrippedString, _XMLAttributeField()] = Field(default="ArtistPeople")
    comparison: Annotated[StrippedString, _XMLAttributeField()] = Field(default="StartsWith")
    value: Annotated[list[str], _XMLAttributeField(), BeforeValidator(to_list)] = Field(default_factory=list)

    # need to make field names title case as they are python keywords
    And: Annotated[_XMLConditions | None, _XMLElementField()] = Field(default=None)
    Or: Annotated[_XMLConditions | None, _XMLElementField()] = Field(default=None)

    @property
    def reference_required(self) -> bool:
        """Whether a reference is required for this condition based on the set value/s."""
        value = next(iter(self.value), None)
        return isinstance(value, str) and value in self.reference_values

    @model_validator(mode="wrap")
    @classmethod
    def _merge_values(cls, data: MutableMapping[str, Any], handler: ModelWrapValidatorHandler[Self]) -> Self:
        if not isinstance(data, MutableMapping):
            return handler(data)

        data = deepcopy(data)
        key = "value"
        if sum(k.lstrip("@").casefold().startswith(key) for k in data) == 1:
            data[key] = next((data.pop(k) for k in tuple(data) if k.lstrip("@").casefold().startswith(key)))
            return handler(data)

        data[key] = [data.pop(k) for k in tuple(data) if k.lstrip("@").casefold().startswith(key)]
        return handler(data)

    @field_validator("field", mode="before", check_fields=True)
    @classmethod
    def _validate_field_is_mapped(cls, field: str) -> str:
        if field not in cls.name_field_map:
            raise MusifyValidationError(f"Unrecognised condition field name: {field}")
        return field

    @model_validator(mode="after")
    def _validate_only_and_either_or_set(self) -> Self:
        if self.And is not None and self.Or is not None:
            raise MusifyValidationError("Condition can only have either 'And' or 'Or' set, not both.")
        return self

    @model_validator(mode="wrap")
    @classmethod
    def _from_comparer(cls, comparer: Comparer, handler: ModelWrapValidatorHandler[Self]) -> Self:
        if not isinstance(comparer, Comparer):
            return handler(comparer)

        model: Self = handler({})
        model.parse_comparer(comparer)
        return model

    @property
    def comparer(self) -> Comparer:
        """Build the comparer for this configuration."""
        value = self.value[0] if len(self.value) == 1 else self.value
        return Comparer(
            condition=self.comparison,
            expected=value if not self.reference_required else None,
            field=self.name_field_map[self.field],
            reference_required=self.reference_required,
        )

    def parse_comparer(self, comparer: Comparer) -> Self:
        """Parse the given ``comparer`` into this model."""
        field = comparer.field
        if field is not None or field not in self.name_field_map:
            field = self.field_name_map[field]

        self.field = field or self.__class__.model_fields["field"].default
        self.comparison = to_pascal(comparer.condition)
        self.value[:] = sorted(to_list(comparer.expected)) or []
        return self

    def parse_sub_comparers(self, combine: bool, comparers: ComparerFilter) -> Self:
        """Parse the given comparers into this model's sub-comparers."""
        self.And = None
        self.Or = None

        if not comparers.ready:
            return self

        sub = _XMLConditions.model_validate(comparers)
        if combine:
            self.And = sub
        else:
            self.Or = sub

        return self


class _XMLConditions(_XMLBaseModel):
    combine_method: Annotated[Literal["Any", "All"], _XMLAttributeField()] = Field(default="All")
    condition: Annotated[
        list[_XMLCondition],
        _XMLElementField(),
        BeforeValidator(to_list)
    ] = Field(default_factory=_XMLCondition)

    @property
    def comparers(self) -> ComparerFilter:
        """Build the comparer filter for this configuration."""
        comparers: dict[Comparer, tuple[bool, ComparerFilter]] = {}
        for condition in self.condition:
            if condition.And:
                value = (True, condition.And.comparers)
            elif condition.Or:
                value = (False, condition.Or.comparers)
            else:
                value = (False, ComparerFilter[LocalTrack]())

            comparers[condition.comparer] = value

        return ComparerFilter[LocalTrack](comparers=comparers, match_all=self.combine_method == "All")

    @model_validator(mode="wrap")
    @classmethod
    def _from_comparers(cls, comparers: ComparerFilter, handler: ModelWrapValidatorHandler[Self]) -> Self:
        if not isinstance(comparers, ComparerFilter):
            return handler(comparers)

        model: Self = handler({})
        model.parse_comparers(comparers)
        return model

    def parse_comparers(self, comparers: ComparerFilter) -> Self:
        """Parse the given ``comparers`` into this model."""
        self.combine_method = "All" if comparers.match_all else "Any"
        self.condition[:] = [
            _XMLCondition.model_validate(comparer).parse_sub_comparers(combine=sub_combine, comparers=sub_comparer)
            for comparer, (sub_combine, sub_comparer) in comparers.comparers.items()
        ]
        return self


class _XMLLimit(_XMLBaseModel):
    filter_duplicates: Annotated[bool, _XMLAttributeField()] = Field(default=False)
    enabled: Annotated[bool, _XMLAttributeField()] = Field(default=False)
    count: Annotated[NonNegativeInt, _XMLAttributeField()] = Field(default=25)
    type: Annotated[StrippedString, _XMLAttributeField()] = Field(default="Items")
    selected_by: Annotated[StrippedString, _XMLAttributeField()] = Field(default="Random")

    @field_validator("type", mode="before", check_fields=True)
    @classmethod
    def _validate_limit_type_exists(cls, kind: str) -> str:
        TypeAdapter(ItemLimiter.model_fields["kind"].annotation).validate_python(kind)
        return kind

    @property
    def limiter(self) -> ItemLimiter | None:
        """Build the limiter for this configuration."""
        if not self.enabled:
            return

        return ItemLimiter(
            limit_by=self.count,
            kind=self.type,
            sorted_by=self.selected_by,
            allowance=1.25,
        )

    @model_validator(mode="wrap")
    @classmethod
    def _from_limiter(cls, limiter: ItemLimiter, handler: ModelWrapValidatorHandler[Self]) -> Self:
        if not isinstance(limiter, ItemLimiter):
            return handler(limiter)

        model: Self = handler({})
        model.parse_limiter(limiter)
        return model

    def parse_limiter(self, limiter: ItemLimiter | None = None, filter_duplicates: bool | None = None) -> Self:
        """Parse the given ``limiter`` into this model."""
        if filter_duplicates is not None:
            self.filter_duplicates = filter_duplicates

        self.enabled = limiter is not None and limiter.limit_by > 0
        if not self.enabled:
            return self

        self.count = limiter.limit_by
        self.type = to_pascal(limiter.kind.name)
        self.selected_by = to_pascal(limiter.sorted_by) or self.__class__.model_fields["selected_by"].default
        return self


class _XMLDisplayField(_XMLBaseModel):
    model_config = ConfigDict(frozen=True)

    code: Annotated[PositiveInt, _XMLAttributeField()]
    width: Annotated[PositiveInt, _XMLAttributeField()]

    @field_validator("code", mode="after", check_fields=True)
    @staticmethod
    def _validate_code_is_mapped(code: int) -> int:
        if code not in _XMLCondition.code_name_map:
            raise MusifyValidationError(f"Unrecognised display field code: {code}")
        return code

    @property
    def field(self) -> str:
        """The field name for this display field."""
        return _XMLCondition.name_field_map[_XMLCondition.code_name_map[self.code]]


class _XMLDisplayGroup(_XMLBaseModel):
    id: Annotated[StrippedString, _XMLAttributeField()] = Field(default="TrackDetail")
    field: Annotated[list[_XMLDisplayField], BeforeValidator(to_list)] = Field(
        default=(
            _XMLDisplayField(code=20, width=16),
            _XMLDisplayField(code=78, width=29),
            _XMLDisplayField(code=65, width=437),
            _XMLDisplayField(code=16, width=75),
            _XMLDisplayField(code=32, width=298),
            _XMLDisplayField(code=30, width=235),
            _XMLDisplayField(code=14, width=78),
        )
    )


class _XMLDisplayFields(_XMLBaseModel):
    group: Annotated[
        list[_XMLDisplayGroup],
        _XMLElementField(),
        BeforeValidator(to_list)
    ] = Field(default_factory=_XMLDisplayGroup)


class _XMLSortBy(_XMLBaseModel):
    # Needed to prevent mistaking this for a multi-field sorter
    model_config = ConfigDict(extra="forbid")

    field: Annotated[NonNegativeInt, _XMLAttributeField()] = Field(default=78)
    order: Annotated[Literal["Ascending", "Descending"], _XMLAttributeField()] = Field(default="Ascending")

    @field_validator("field", mode="after", check_fields=True)
    @staticmethod
    def _validate_field_is_mapped(code: int) -> int:
        if code not in _XMLCondition.code_name_map:
            raise MusifyValidationError(f"Unrecognised sort field code: {code}")
        return code

    @property
    def field_name(self) -> str:
        """The field name for this display field."""
        return _XMLCondition.name_field_map[_XMLCondition.code_name_map[self.field]]

    @property
    def sort_fields(self) -> dict[str, bool]:
        """Fields to sort by mapped to expected field names and whether to reverse them."""
        return {self.field_name: self.order == "Descending"}

    @model_validator(mode="wrap")
    @classmethod
    def _from_sorter(cls, sorter: ItemSorter, handler: ModelWrapValidatorHandler[Self]) -> Self:
        if not isinstance(sorter, ItemSorter):
            return handler(sorter)

        model: Self = handler({})
        model.parse_sorter(sorter)
        return model

    def parse_sorter(self, sorter: ItemSorter) -> Self:
        """Parse the given ``sorter`` into this model."""
        if len(sorter.sort_fields) > 1:
            raise MusifyValueError("Only use this sorter for single-field sorts.")

        if not sorter.sort_fields:
            self.field = self.__class__.model_fields["field"].default
            self.order = self.__class__.model_fields["order"].default
            return self

        field, reverse = next(iter(sorter.sort_fields.items()))
        field_code = _XMLCondition.name_code_map.get(_XMLCondition.field_name_map.get(field))
        if field_code is None:
            raise MusifyValueError(f"Field code mapping not found for field: {field}")

        self.field = field_code
        self.order = "Descending" if reverse else "Ascending"

        return self


class _XMLDefinedSort(_XMLBaseModel):
    # Needed to prevent mistaking this for a single-field sorter
    model_config = ConfigDict(extra="forbid")

    fields_map: ClassVar[dict[int, dict[str, bool]]] = {
        6: {
            "Album": False,
            "DiscNo": False,
            "TrackNo": False,
            "FileName": False
        }
        # TODO: implement field_code 78 - manual order according to the order of tracks found
        #  in the MusicBee library file for a given playlist.
    }

    id: Annotated[PositiveInt, _XMLAttributeField()]

    @field_validator("id", mode="after", check_fields=True)
    @classmethod
    def _validate_id_is_mapped(cls, value: int) -> int:
        if value not in cls.fields_map:
            raise MusifyValidationError(
                f"Unrecognised defined sort ID: {value}. Available IDs: {", ".join(map(str, cls.fields_map))}"
            )
        return value

    @property
    def sort_fields(self) -> dict[str, bool]:
        """Fields to sort by mapped to expected field names and whether to reverse them."""
        fields = self.fields_map[self.id]
        return {_XMLCondition.name_field_map[field]: reverse for field, reverse in fields.items()}

    @model_validator(mode="wrap")
    @classmethod
    def _from_sorter(cls, sorter: ItemSorter, handler: ModelWrapValidatorHandler[Self]) -> Self:
        if not isinstance(sorter, ItemSorter):
            return handler(sorter)

        # just select any random id for now, will be overwritten in parse_sorter
        model: Self = handler({"id": choice(tuple(cls.fields_map.keys()))})
        model.parse_sorter(sorter)
        return model

    def parse_sorter(self, sorter: ItemSorter) -> Self:
        """Parse the given ``sorter`` into this model."""
        if len(sorter.sort_fields) <= 1:
            raise MusifyValueError("Only use this sorter for multi-field sorts.")

        unknown_fields = [
            field for field in sorter.sort_fields
            if _XMLCondition.name_code_map.get(_XMLCondition.field_name_map.get(field)) is None
        ]
        if unknown_fields:
            raise MusifyValueError(f"Field code mapping not found for fields: {', '.join(unknown_fields)}")

        fields = {_XMLCondition.field_name_map[k]: v for k, v in sorter.sort_fields.items()}
        sort_id = next((code for code, val in self.fields_map.items() if val == fields), None)
        if sort_id is None:
            raise MusifyValueError(f"No sort defined for the fields: {fields}")

        self.id = sort_id
        return self


class _XMLSource(_XMLBaseModel):
    model_config = ConfigDict()
    type: Annotated[PositiveInt, _XMLAttributeField()] = Field(default=1)
    description: Annotated[StrippedString | None, _XMLElementField()] = Field(default=None)

    conditions: Annotated[_XMLConditions, _XMLElementField()] = Field(default_factory=_XMLConditions)
    limit: Annotated[_XMLLimit, _XMLElementField()] = Field(default_factory=_XMLLimit)
    sort_by: Annotated[_XMLSortBy | _XMLDefinedSort | None, _XMLElementField()] = Field(
        validation_alias=AliasChoices("DefinedSort", "SortBy", ),
        default=None,
    )
    fields: Annotated[_XMLDisplayFields, _XMLElementField()] = Field(default_factory=_XMLDisplayFields)

    exceptions_include: Annotated[set[StrippedString] | None, _XMLElementField()] = Field(default=None)
    exceptions: Annotated[set[StrippedString] | None, _XMLElementField()] = Field(default=None)

    @field_validator("exceptions", "exceptions_include", mode="before", check_fields=True)
    @staticmethod
    def _split_exceptions[T: str](value: T) -> T | set[str]:
        if not isinstance(value, str):
            return value
        return set(value.split("|"))

    @field_serializer("exceptions", "exceptions_include", check_fields=True)
    def _join_exceptions(self, value: Collection[str]) -> str | None:
        return "|".join(sorted(value)) if value else None

    @model_serializer(mode="wrap")
    def _order_keys(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        dump = handler(self)
        if isinstance(self.sort_by, _XMLDefinedSort):  # remap key to match single-field sorter
            order = list(dump.keys())

            try:
                dump[key := "DefinedSort"] = dump.pop(alias := "SortBy")
                order[order.index(alias)] = key
                dump = dict(sorted(dump.items(), key=lambda it: order.index(it[0])))
            except KeyError:
                pass

        return self._serialize_xml(dump)

    def parse_matcher(self, matcher: AutoMatcher | None = None) -> Self:
        """Parse the given ``matcher`` into this configuration."""
        if matcher is None:
            self.conditions = _XMLConditions()
            self.exceptions_include = None
            self.exceptions = None
            return

        self.conditions = _XMLConditions.model_validate(matcher.compare)
        self.exceptions_include = matcher.include.values or None
        self.exceptions = matcher.exclude.values or None
        return self

    def parse_sorter(self, sorter: ItemSorter | None = None) -> Self:
        """Parse the given ``sorter`` into this configuration."""
        self.sort_by = None
        if sorter is None or not sorter.sort_fields:
            return self

        if len(sorter.sort_fields) == 1:
            self.sort_by = _XMLSortBy.model_validate(sorter)
        else:
            self.sort_by = _XMLDefinedSort.model_validate(sorter)

        return self


class _XMLSmartPlaylist(_XMLBaseModel):
    save_static_copy: Annotated[bool, _XMLAttributeField()] = Field(default=False)
    live_updating: Annotated[bool, _XMLAttributeField()] = Field(default=True)
    layout: Annotated[NonNegativeInt, _XMLAttributeField()] = Field(default=4)
    layout_group_by: Annotated[NonNegativeInt, _XMLAttributeField()] = Field(default=0)
    shuffle_mode: Annotated[StrippedString | None, _XMLAttributeField()] = Field(default=None)
    shuffle_same_artist_weight: Annotated[float, _XMLAttributeField(), Field(ge=-1.0, le=1.0)] = Field(default=0.5)
    group_by: Annotated[StrippedString, _XMLAttributeField()] = Field(default="track")
    consolidate_albums: Annotated[bool, _XMLAttributeField()] = Field(default=False)
    music_library_path: Annotated[StrippedString | None, _XMLAttributeField()] = Field(default=None)

    source: Annotated[_XMLSource, _XMLElementField()] = Field(default_factory=_XMLSource)

    @property
    def matcher(self) -> AutoMatcher:
        """Build the matcher for this configuration."""
        include = PathsFilter(values=self.source.exceptions_include or set())
        exclude = PathsFilter(values=self.source.exceptions or set())

        # grouping by track is equivalent to no grouping
        group_by = self.group_by or "track"
        if group_by == "track":
            group_by = None

        return AutoMatcher(
            compare=self.source.conditions.comparers,
            include=include,
            exclude=exclude,
            group_by=group_by,
        )

    def parse_matcher(self, matcher: AutoMatcher | None = None) -> Self:
        """Parse the given ``matcher`` into this configuration."""
        self.source.parse_matcher(matcher)

        group_by_default = self.__class__.model_fields["group_by"].default
        if matcher is None:
            self.group_by = group_by_default
            return self

        self.group_by = matcher.group_by or group_by_default
        return self

    @property
    def sorter(self) -> ItemSorter:
        """Build the sorter for this configuration."""
        return ItemSorter(
            sort_fields=self.source.sort_by.sort_fields if self.source.sort_by is not None else {},
            shuffle_mode=self.shuffle_mode,
            shuffle_weight=self.shuffle_same_artist_weight,
        )

    def parse_sorter(self, sorter: ItemSorter | None = None) -> Self:
        """Parse the given ``sorter`` into this configuration."""
        self.source.parse_sorter(sorter)

        if sorter is None:
            self.shuffle_mode = None
            self.shuffle_same_artist_weight = self.__class__.model_fields["shuffle_same_artist_weight"].default
            return self

        self.shuffle_mode = to_pascal(sorter.shuffle_mode.name) if sorter.shuffle_mode is not None else None
        self.shuffle_same_artist_weight = sorter.shuffle_weight
        return self


class _XMLRoot(_XMLBaseModel):
    __required_modules__ = {"xmltodict": xmltodict}

    smart_playlist: Annotated[_XMLSmartPlaylist, _XMLElementField()] = Field(default_factory=_XMLSmartPlaylist)

    @model_validator(mode="wrap")
    @classmethod
    def parse_xml(cls, value: str, handler: ModelWrapValidatorHandler[Self]) -> Self:
        """Parse the given XML string."""
        if not isinstance(value, str):
            return handler(value)

        xml = xmltodict.parse(value, attr_prefix="")
        return handler(xml)

    def unparse_xml(self) -> str:
        """Dump the model to an XML string."""
        xml = xmltodict.unparse(
            self.model_dump_xml(),
            short_empty_elements=True,
            attr_prefix=_XMLAttributeField.attr_prefix,
            pretty=True,
            indent=" " * 2,
        )
        return xml.replace("/>", " />")
