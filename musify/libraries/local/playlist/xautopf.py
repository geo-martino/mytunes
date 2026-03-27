"""
The XAutoPF implementation of a :py:class:`LocalPlaylist`.
"""
from collections.abc import Collection, Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Self

from musify.base import MusifyItem, Result
from musify.exception import FieldError, MusifyImportError
from musify.field import Fields, Field, TagFields
from musify.file.base import File
from musify.file.path_mapper import PathMapper
from musify.libraries.local.playlist.base import LocalPlaylist
from musify.libraries.local.track import LocalTrack
from musify.libraries.remote.core.wrangle import RemoteDataWrangler
from musify.printer import PrettyPrinter
from musify.processors.compare import Comparer
from musify.processors.exception import SorterProcessorError
from musify.processors.filter import FilterDefinedList, FilterComparers
from musify.processors.filter_matcher import FilterMatcher
from musify.processors.limit import ItemLimiter, LimitType
from musify.processors.sort import ItemSorter, ShuffleMode
from musify.utils import to_collection

try:
    import xmltodict
except ImportError:
    xmltodict = None

REQUIRED_MODULES = [xmltodict]

AutoMatcher = FilterMatcher[
    LocalTrack, FilterDefinedList[LocalTrack], FilterDefinedList[LocalTrack], FilterComparers[LocalTrack]
]


@dataclass(frozen=True)
class SyncResultXAutoPF(Result):
    """Stores the results of a sync with a local XAutoPF playlist."""
    #: The total number of tracks in the playlist before the sync.
    start: int
    #: The number of tracks that matched the include settings before the sync.
    start_included: int
    #: The number of tracks that matched the exclude settings before the sync.
    start_excluded: int
    #: The number of tracks that matched all the :py:class:`Comparer` settings before the sync.
    start_compared: int
    #: Was a limiter present on the playlist before the sync.
    start_limiter: bool
    #: Was a sorter present on the playlist before the sync.
    start_sorter: bool

    #: The total number of tracks in the playlist after the sync.
    final: int
    #: The number of tracks that matched the include settings after the sync.
    final_included: int
    #: The number of tracks that matched the exclude settings after the sync.
    final_excluded: int
    #: The number of tracks that matched all the :py:class:`Comparer` settings after the sync.
    final_compared: int
    #: Was a limiter present on the playlist after the sync.
    final_limiter: bool
    #: Was a sorter present on the playlist after the sync.
    final_sorter: bool


class XAutoPF(LocalPlaylist[AutoMatcher]):
    """
    For reading and writing data from MusicBee's auto-playlist format.

    :param path: Absolute path of the playlist.
        If the playlist ``path`` given does not exist, a new playlist will be created on :py:meth:`save`
    :param path_mapper: Optionally, provide a :py:class:`PathMapper` for paths stored in the playlist file.
        Useful if the playlist file contains relative paths and/or paths for other systems that need to be
        mapped to absolute, system-specific paths to be loaded and back again when saved.
    :param remote_wrangler: Not used by this object.
    """

    __slots__ = ("_parser", "_limiter_deduplication")
    __attributes_ignore__ = ("limiter_deduplication",)

    valid_extensions = frozenset({".xautopf"})

    #: The initial values to use as the base XML when creating a new XAutoPF file from scratch.
    #: Certain settings in the 'Source' key relating to processors that this program recognises
    #: will be set on initialisation. Hence, any default values assigned to these keys will be overridden.
    default_xml = {
        "SmartPlaylist": {
            "@SaveStaticCopy": "False",
            "@LiveUpdating": "True",
            "@Layout": "4",
            "@LayoutGroupBy": "0",
            "@ConsolidateAlbums": "False",
            "@MusicLibraryPath": "",
            "Source": {"@Type": "1", "Description": None}
        }
    }

    @property
    def description(self):
        return self._parser.description

    @description.setter
    def description(self, value: str | None):
        self._parser.description = value

    @property
    def limiter_deduplication(self) -> bool:
        """This setting controls whether duplicates should be filtered out before running limiter operations."""
        return self._limiter_deduplication

    @limiter_deduplication.setter
    def limiter_deduplication(self, value: bool):
        self._limiter_deduplication = value

    @property
    def image_links(self):
        return {}

    def __init__(
            self,
            path: str | Path,
            path_mapper: PathMapper = PathMapper(),
            remote_wrangler: RemoteDataWrangler = None
    ):
        if xmltodict is None:
            raise MusifyImportError(f"Cannot create {self.__class__.__name__} object. Required modules: xmltodict")

        super().__init__(path=path, path_mapper=path_mapper, remote_wrangler=remote_wrangler)

        self._parser: XMLPlaylistParser | None = None
        self._limiter_deduplication: bool = False

    async def load(self, tracks: Collection[LocalTrack] = ()) -> Self:
        """
        Read the playlist file and update the tracks in this playlist instance.

        :param tracks: Available Tracks to search through for matches.
            If no tracks are given, the playlist will be loaded empty.
        :return: Self
        """
        self._parser = XMLPlaylistParser(path=self.path, path_mapper=self.path_mapper)
        if self.path.is_file():
            await self._parser.load()
        else:  # this is a new playlist, assign default values to parser
            self._parser.xml = deepcopy(self.default_xml)
            self._parser.parse_matcher()
            self._parser.parse_limiter()
            self._parser.parse_sorter()

        self.matcher = self._parser.get_matcher()
        self.limiter = self._parser.get_limiter()
        self.sorter = self._parser.get_sorter()
        self._limiter_deduplication = self._parser.limiter_deduplication

        tracks_list = list(tracks)
        self.sorter.sort_by_field(tracks_list, field=Fields.LAST_PLAYED, reverse=True)

        self._match(tracks=tracks, reference=tracks_list[0] if len(tracks) > 0 else None)
        self._limit(ignore=self.matcher.exclude)
        self._sort()

        self._original = self.tracks.copy()

        return self

    def _limit(self, ignore: Collection[LocalTrack]) -> None:
        if self.limiter is not None and self.tracks is not None and self.limiter_deduplication:
            # preprocess tracks by applying deduplication first before sending to the actual limiter
            tracks_keys_seen = set()
            tracks_deduplicated: list[LocalTrack] = []

            for track in self.tracks:
                track_key = "_".join([track.title, track.artist])
                if track in ignore or track_key not in tracks_keys_seen:
                    tracks_keys_seen.add(track_key)
                    tracks_deduplicated.append(track)

            self.tracks = tracks_deduplicated
        super()._limit(ignore=ignore)

    async def save(self, dry_run: bool = True, *_, **__) -> SyncResultXAutoPF:
        """
        Write the tracks in this Playlist and its settings (if applicable) to file.

        :param dry_run: Run function, but do not modify the file on the disk.
        :return: The results of the sync as a :py:class:`SyncResultXAutoPF` object.
        """
        initial = deepcopy(self._parser)
        initial_count = len(self._original)

        parser = self._parser if not dry_run else deepcopy(self._parser)
        parser.parse_matcher(self.matcher)
        parser.parse_exception_paths(self.matcher, items=self.tracks, original=self._original)
        parser.parse_limiter(self.limiter, deduplicate=self.limiter_deduplication)
        parser.parse_sorter(self.sorter)
        await parser.save(dry_run=dry_run)

        if not dry_run:
            self._original = self.tracks.copy()

        def _get_paths_sum(psr: XMLPlaylistParser, key: str) -> int:
            if not (value := psr.xml_source.get(key)):
                return 0
            return sum(1 for p in value.split("|") if p)

        return SyncResultXAutoPF(
            start=initial_count,
            start_included=_get_paths_sum(initial, "ExceptionsInclude"),
            start_excluded=_get_paths_sum(initial, "Exceptions"),
            start_compared=len(initial.xml_source["Conditions"].get("Condition", [])),
            start_limiter=initial.xml_source["Limit"].get("@Enabled", "False") == "True",
            start_sorter=len(initial.xml_source.get("SortBy", initial.xml_source.get("DefinedSort", []))) > 0,
            final=len(self.tracks),
            final_included=_get_paths_sum(parser, "ExceptionsInclude"),
            final_excluded=_get_paths_sum(parser, "Exceptions"),
            final_compared=len(parser.xml_source["Conditions"].get("Condition", [])),
            final_limiter=parser.xml_source["Limit"].get("@Enabled", "False") == "True",
            final_sorter=len(parser.xml_source.get("SortBy", parser.xml_source.get("DefinedSort", []))) > 0,
        )


class XMLPlaylistParser(File, PrettyPrinter):

    __slots__ = ("_path", "path_mapper", "xml")

    # noinspection SpellCheckingInspection
    #: Map of MusicBee field key name to Field enum
    name_field_map = {
        "None": None,
        "Title": Fields.TITLE,
        "ArtistPeople": Fields.ARTIST,
        "Album": Fields.ALBUM,  # album ignoring articles like 'the' and 'a' etc.
        "Album Artist": Fields.ALBUM_ARTIST,
        "TrackNo": Fields.TRACK_NUMBER,
        "TrackCount": Fields.TRACK_TOTAL,
        "GenreSplits": Fields.GENRES,
        "Year": Fields.YEAR,  # could also be 'YearOnly'?
        "BeatsPerMin": Fields.BPM,
        "DiscNo": Fields.DISC_NUMBER,
        "DiscCount": Fields.DISC_TOTAL,
        # "": Fields.COMPILATION,  # unmapped for compare
        "Comment": Fields.COMMENTS,
        "FileDuration": Fields.LENGTH,
        "Rating": Fields.RATING,
        # "ComposerPeople": Fields.COMPOSER,  # currently not supported by this program
        # "Conductor": Fields.CONDUCTOR,  # currently not supported by this program
        # "Publisher": Fields.PUBLISHER,  # currently not supported by this program
        "FilePath": Fields.PATH,
        "FolderName": Fields.FOLDER,
        "FileName": Fields.FILENAME,
        "FileExtension": Fields.EXT,
        # "": Fields.SIZE,  # unmapped for compare
        "FileKind": Fields.TYPE,
        "FileBitrate": Fields.BIT_RATE,
        "BitDepth": Fields.BIT_DEPTH,
        "FileSampleRate": Fields.SAMPLE_RATE,
        "FileChannels": Fields.CHANNELS,
        # "": Fields.DATE_CREATED,  # unmapped for compare
        "FileDateModified": Fields.DATE_MODIFIED,
        "FileDateAdded": Fields.DATE_ADDED,
        "FileLastPlayed": Fields.LAST_PLAYED,
        "FilePlayCount": Fields.PLAY_COUNT,
    }
    #: Map of Field enum to MusicBee field key name
    field_name_map = {field: name for name, field in name_field_map.items()}

    #: Settings for custom sort codes.
    defined_sort: dict[int, Mapping[Field, bool]] = {
        6: {
            Fields.ALBUM: False,
            Fields.DISC_NUMBER: False,
            Fields.TRACK_NUMBER: False,
            Fields.FILENAME: False
        }
        # TODO: implement field_code 78 - manual order according to the order of tracks found
        #  in the MusicBee library file for a given playlist.
    }
    #: The default/manual sort code
    default_sort = 78
    #: The default setting to use for the GroupBy setting
    default_group_by = "track"

    @property
    def path(self) -> Path:
        return self._path

    @property
    def xml_smart_playlist(self) -> dict[str, Any]:
        """The smart playlist data part of the loaded XML playlist data"""
        return self.xml["SmartPlaylist"]

    @property
    def xml_source(self) -> dict[str, Any]:
        """The source data part of the loaded XML playlist data"""
        return self.xml_smart_playlist["Source"]

    @property
    def description(self):
        """The description value of the XML playlist data"""
        return self.xml_source["Description"]

    @description.setter
    def description(self, value: str | None):
        """The description value of the XML playlist data"""
        if value:
            self.xml_source["Description"] = value
        else:
            self.xml_source.pop("Description", None)

    def __init__(self, path: str | Path, path_mapper: PathMapper = PathMapper()):
        if xmltodict is None:
            raise MusifyImportError(f"Cannot create {self.__class__.__name__} object. Required modules: xmltodict")

        self._path = Path(path)
        #: Maps paths stored in the playlist file.
        self.path_mapper = path_mapper
        #: A map representation of the loaded XML playlist data
        self.xml: dict[str, Any] = {}

    async def load(self) -> None:
        """Load ``xml`` object from the disk"""
        with open(self.path, "r", encoding="utf-8") as file:
            self.xml: dict[str, Any] = xmltodict.parse(file.read())

    async def save(self, dry_run: bool = True, *_, **__) -> None:
        """Save ``xml`` object to the disk"""
        if dry_run:
            return
        with open(self.path, 'w', encoding="utf-8") as file:
            xml_str = xmltodict.unparse(self.xml, pretty=True, short_empty_elements=True)
            file.write(xml_str.replace("/>", " />").replace('\t', '  '))

    def _get_comparer(self, xml: Mapping[str, Any]) -> Comparer:
        """
        Initialise and return a :py:class:`Comparer` from the relevant chunk of settings in ``xml`` playlist data.

        :param xml: The relevant chunk to generate a single :py:class:`Comparer` as found in
            the loaded XML object for this playlist.
            This function expects to be given only the XML part related to one Comparer condition.
        :return: The initialised :py:class:`Comparer`.
        """
        field_name = xml.get("@Field", "None")
        field: Field = self.name_field_map.get(field_name)
        if field is None:
            raise FieldError("Unrecognised field name", field=field_name)

        expected: tuple[str, ...] | None = tuple(v for k, v in xml.items() if k.startswith("@Value"))
        reference_required = next(iter(expected), None) == "[playing track]"
        if len(expected) == 0 or expected[0] == "[playing track]":
            expected = None

        return Comparer(
            condition=xml["@Comparison"], expected=expected, field=field, reference_required=reference_required
        )

    def _get_xml_from_comparer(self, comparer: Comparer | None = None) -> dict[str, Any]:
        """Parse the given ``comparer`` to its XML playlist representation."""
        if comparer is None:  # default value
            return {"@Field": "ArtistPeople", "@Comparison": "StartsWith", "@Value": ""}

        field_name = self.field_name_map.get(comparer.field)
        if field_name is None:
            raise FieldError("Unrecognised field", field=comparer.field)

        condition = "[playing track]" if comparer.reference_required else self._snake_to_pascal(comparer.condition)

        xml: dict[str, Any] = {"@Field": field_name, "@Comparison": condition}

        if comparer.expected is None:
            pass
        elif len(comparer.expected) == 0:
            xml["@Value"] = ""
        elif len(comparer.expected) == 1:
            xml["@Value"] = str(comparer.expected[0])
        else:
            for i, value in enumerate(comparer.expected, 1):
                xml[f"@Value{i}"] = str(value)

        return xml

    def get_matcher(self) -> AutoMatcher:
        """Initialise and return a :py:class:`FilterMatcher` object from loaded XML playlist data."""
        def get_exceptions(key: str) -> set[Path]:
            """Get exception paths from XML to include/exclude even if they meet/don't meet match compare conditions"""
            if not (raw_str := self.xml_source.get(key)):
                return set()

            paths = set(raw_str.split("|"))
            return set(map(Path, self.path_mapper.map_many(paths, check_existence=True)))

        include = get_exceptions("ExceptionsInclude")
        exclude = get_exceptions("Exceptions")

        comparers: dict[Comparer, tuple[bool, FilterComparers]] = {}
        for condition in to_collection(self.xml_source["Conditions"]["Condition"]):
            if any(key in condition for key in {"And", "Or"}):
                combine = "And" in condition
                conditions = condition["And" if combine else "Or"]
                sub_filter = FilterComparers(
                    comparers=[self._get_comparer(sub) for sub in to_collection(conditions["Condition"])],
                    match_all=conditions["@CombineMethod"] == "All"
                )
            else:
                combine = False
                sub_filter = FilterComparers()

            comparers[self._get_comparer(xml=condition)] = (combine, sub_filter)

        dummy_conditions = {"starts_with", "contains"}
        if len(comparers) == 1 and not next(iter(comparers.values()))[1].ready:
            # when user has not set an explicit comparer, a single empty 'allow all' comparer is assigned
            # check for this 'allow all' comparer and remove it if present to speed up comparisons
            c = next(iter(comparers))
            is_dummy_condition = any(cond in c.condition.casefold() for cond in dummy_conditions)
            if is_dummy_condition and len(c.expected) == 1 and not c.expected[0]:
                comparers = {}

        filter_include = FilterDefinedList[LocalTrack](values=include)
        filter_exclude = FilterDefinedList[LocalTrack](values=exclude)
        filter_compare = FilterComparers[LocalTrack](
            comparers, match_all=self.xml_source["Conditions"]["@CombineMethod"] == "All"
        )

        filter_include.transform = lambda x: Path(self.path_mapper.map(x, check_existence=False))
        filter_exclude.transform = lambda x: Path(self.path_mapper.map(x, check_existence=False))

        group_by_value = self._pascal_to_snake(self.xml_smart_playlist["@GroupBy"])
        group_by = None if group_by_value == self.default_group_by else TagFields.from_name(group_by_value)[0]

        return FilterMatcher(
            include=filter_include, exclude=filter_exclude, comparers=filter_compare, group_by=group_by
        )

    def parse_matcher(self, matcher: FilterMatcher | None = None) -> None:
        """
        Update the loaded ``xml`` object by parsing the given ``matcher`` to its XML playlist representation.
        Does not extract exception paths (i.e. include/exclude attributes).
        """
        if matcher is None or not matcher.ready:
            self.xml_smart_playlist["@GroupBy"] = self.default_group_by
            self.xml_source["Conditions"] = {"@CombineMethod": "All"} | {"Condition": self._get_xml_from_comparer()}
            return

        group_by = matcher.group_by.name.lower() if matcher.group_by else self.default_group_by
        self.xml_smart_playlist["@GroupBy"] = group_by.lower()
        self.xml_source["Conditions"] = self._parse_filter_comparer(matcher.comparers)

    def _parse_filter_comparer(self, filter_: FilterComparers) -> dict[str, Any]:
        combine_method = "All" if filter_.match_all else "Any"
        conditions: list[dict[str, Any]] = []
        for comparer, (combine, sub_filter) in filter_.comparers.items():
            condition = self._get_xml_from_comparer(comparer)
            if sub_filter.ready:
                combine_key = "And" if combine else "Or"
                condition[combine_key] = self._parse_filter_comparer(sub_filter)

            conditions.append(condition)

        if len(conditions) == 0:  # assign the default value when no comparers present
            conditions.append(self._get_xml_from_comparer())

        return {
            "@CombineMethod": combine_method,
            "Condition": conditions[0] if len(conditions) == 1 else conditions
        }

    def parse_exception_paths(
            self, matcher: FilterMatcher | None, items: list[File], original: list[File | MusifyItem]
    ) -> None:
        """
        Parse the exception paths (i.e. include/exclude attributes) for the given ``matcher``
        to its XML playlist representation. Does not extract any other attributes from the ``matcher``.

        :param matcher: The :py:class:`FilterMatcher` to parse.
        :param items: The items to export.
        :param original: The original items matched from the settings in the original file.
        """
        if matcher is None:
            self.xml_source.pop("ExceptionsInclude", None)
            self.xml_source.pop("Exceptions", None)
            return

        if not isinstance(matcher.include, FilterDefinedList) and not isinstance(matcher.exclude, FilterDefinedList):
            matcher.logger.warning(
                "Cannot export this filter to XML: Include and Exclude settings must both be list filters"
            )
            return

        items_mapped: dict[Path, File] = {item.path: item for item in items}

        if matcher.comparers:
            # match again on current conditions to check for differences from original list
            # which ensures that the paths included in the XML output
            # do not include paths that match any of the comparer or group_by conditions

            # copy the list of tracks as the sorter will modify the list order
            original = original.copy()
            # get the last played track as reference in case comparer is looking for the playing tracks as reference
            ItemSorter.sort_by_field(original, field=Fields.LAST_PLAYED, reverse=True)

            matched_mapped: dict[Path, File] = {
                item.path: item for item in matcher.comparers(original, reference=next(iter(original), None))
            } if matcher.comparers.ready else {}
            # noinspection PyProtectedMember
            matched_mapped |= {
                item.path: item for item in matcher._get_group_by_results(original, matched_mapped.values())
            }

            # get new include/exclude paths based on the leftovers after matching on comparers and group_by settings
            matcher.exclude.values = list(matched_mapped.keys() - items_mapped)
            matcher.include.values = [v for v in list(items_mapped - matched_mapped.keys()) if v not in matcher.exclude]
        else:
            matched_mapped = items_mapped

        include_items = tuple(items_mapped[path] for path in matcher.include if path in items_mapped)
        exclude_items = tuple(matched_mapped[path] for path in matcher.exclude if path in matched_mapped)

        if len(include_items) > 0:
            include_paths = self.path_mapper.unmap_many(include_items, check_existence=False)
            self.xml_source["ExceptionsInclude"] = "|".join(include_paths)
        if len(exclude_items) > 0:
            exclude_paths = self.path_mapper.unmap_many(exclude_items, check_existence=False)
            self.xml_source["Exceptions"] = "|".join(exclude_paths)

    def get_limiter(self) -> ItemLimiter | None:
        """Initialise and return a :py:class:`ItemLimiter` object from loaded XML playlist data."""
        conditions: Mapping[str, str] = self.xml_source["Limit"]
        if conditions["@Enabled"] != "True":
            return

        # MusicBee appears to have some extra allowance on time and byte limits of ~1.25
        return ItemLimiter(
            limit=int(conditions["@Count"]),
            on=LimitType.from_name(conditions["@Type"])[0],
            sorted_by=conditions["@SelectedBy"],
            allowance=1.25
        )

    @property
    def limiter_deduplication(self) -> bool:
        """This setting controls whether duplicates should be filtered out before running limiter operations."""
        return self.xml_source["Limit"]["@FilterDuplicates"] == "True"

    def parse_limiter(self, limiter: ItemLimiter | None = None, deduplicate: bool = False) -> None:
        """Update the loaded ``xml`` object by parsing the given ``limiter`` to its XML playlist representation."""
        if limiter is None:  # default value
            xml = {
                "@FilterDuplicates": str(deduplicate).title(),
                "@Enabled": "False",
                "@Count": "25",
                "@Type": "Items",
                "@SelectedBy": "Random"
            }
        else:
            xml = {
                "@FilterDuplicates": str(deduplicate).title(),
                "@Enabled": "True",
                "@Count": str(limiter.limit_max),
                "@Type": limiter.kind.name.title(),
                "@SelectedBy": self._snake_to_pascal(limiter.limit_sort)
            }

        self.xml_source["Limit"] = xml

    def get_sorter(self) -> ItemSorter | None:
        """Initialise and return a :py:class:`ItemLimiter` object from loaded XML playlist data."""
        fields: Sequence[Field] | Mapping[Field | bool] = ()

        if "SortBy" in self.xml_source:
            field_code = int(self.xml_source["SortBy"].get("@Field", 0))
        elif "DefinedSort" in self.xml_source:
            field_code = int(self.xml_source["DefinedSort"]["@Id"])
        else:
            return

        if field_code in self.defined_sort:
            fields = self.defined_sort[field_code]
            return ItemSorter(fields=fields)
        elif field_code != self.default_sort:
            field = Fields.from_value(field_code)[0]

            if "SortBy" in self.xml_source:
                fields = {field: self.xml_source["SortBy"]["@Order"] == "Descending"}
            elif "DefinedSort" in self.xml_source:
                fields = [field]
            else:
                raise SorterProcessorError("Sort type in XML not recognised")

        shuffle_mode_value = self._pascal_to_snake(self.xml_smart_playlist["@ShuffleMode"])
        if not fields and shuffle_mode_value != "none":
            shuffle_mode = ShuffleMode.from_name(shuffle_mode_value)[0]
            shuffle_weight = float(self.xml_smart_playlist.get("@ShuffleSameArtistWeight", 0))

            return ItemSorter(fields=fields, shuffle_mode=shuffle_mode, shuffle_weight=shuffle_weight)

        # TODO: remove defined_sort workaround here, should use manual sort when no `fields` - see self.defined_sort
        return ItemSorter(fields=fields or next(iter(self.defined_sort.values())))

    def parse_sorter(self, sorter: ItemSorter | None = None) -> None:
        """Update the loaded ``xml`` object by parsing the given ``sorter`` to its XML playlist representation."""
        self.xml_source.pop("SortBy", None)
        self.xml_source.pop("DefinedSort", None)

        if sorter is None:  # default value
            self.xml_smart_playlist["@ShuffleMode"] = "None"
            self.xml_smart_playlist["@ShuffleSameArtistWeight"] = "0.5"
            self.xml_source["SortBy"] = {"@Field": str(self.default_sort), "@Order": "Ascending"}
            return

        shuffle_mode = "None" if sorter.shuffle_mode is None else self._snake_to_pascal(sorter.shuffle_mode.name)
        self.xml_smart_playlist["@ShuffleMode"] = shuffle_mode
        self.xml_smart_playlist["@ShuffleSameArtistWeight"] = str(sorter.shuffle_weight)

        defined_sort_key = next((key for key, value in self.defined_sort.items() if value == sorter.sort_fields), None)
        if defined_sort_key is not None:
            self.xml_source["DefinedSort"] = {"@Id": str(defined_sort_key)}
            return

        if len(sorter.sort_fields) > 1:
            raise SorterProcessorError(
                "Cannot generate an XML representation of a mapping of many sort fields unless they have "
                "a defined sort ID. To parse these fields to XML, define this map in the 'defined_sort' "
                f"class attribute of this parser | {sorter.sort_fields}"
            )

        field, reverse_sort = next(iter(sorter.sort_fields.items()), (None, False))
        self.xml_source["SortBy"] = {
            "@Field": str(field.value if field is not None else self.default_sort),
            "@Order": "Descending" if reverse_sort else "Ascending"
        }

    def as_dict(self):
        return {"path": self.path, "path_mapper": self.path_mapper}
