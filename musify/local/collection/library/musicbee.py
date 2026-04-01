"""
An implementation of :py:class:`LocalLibrary` for the MusicBee library manager.
Reads library/settings files from MusicBee to load and enrich playlist/track etc. data.
"""
import hashlib
import os
import re
from collections.abc import Mapping, Sequence, Iterator, MutableMapping
from datetime import datetime
from pathlib import Path
from typing import Any, ClassVar, Self, Annotated, final
from urllib.parse import quote, unquote

from aiorequestful.types import Number
from pydantic import Field, PrivateAttr, DirectoryPath, model_validator, ModelWrapValidatorHandler, BeforeValidator, \
    FilePath

from musify._types import to_set
from musify.exception import MusifyTypeError, MusifyValueError
from musify.local.collection.library._base import LocalLibrary
from musify.local.collection.playlist import LocalPlaylist
from musify.local.exception import XMLReaderError, FileDoesNotExistError
from musify.local.item.track import LocalTrack
from musify.models import BaseModel, makecls
from musify.models.properties.file import IsReadableFile, IsWriteableFile, PathStemMapper, IsLocalFile

try:
    import xmltodict
    from lxml import etree
    # noinspection PyProtectedMember
    from lxml.etree import _Element as Element
except ImportError:
    xmltodict = None
    etree = None

    from typing import Never
    Element = Never


# noinspection PyFinal
@final
class MusicBee(LocalLibrary, IsReadableFile, IsWriteableFile, IsLocalFile, metaclass=makecls()):
    """
    Represents a local MusicBee library, providing various methods for manipulating
    tracks and playlists across an entire local library collection.
    """
    __final__ = True
    __required_modules__ = {"xmltodict": xmltodict, "etree": etree}
    __supported_extensions__ = frozenset({"xml"})

    source: ClassVar[str] = "local"

    #: The relative path of the MusicBee settings file in the ``musicbee_folder``.
    _xml_settings_path: ClassVar[Path] = Path("MusicBeeLibrarySettings.ini")
    #: The relative path of the MusicBee library file in the ``musicbee_folder``.
    _xml_library_path: ClassVar[Path] = Path("iTunes Music Library.xml")
    #: A list of keys for the XML library that need to be processed as system paths.
    _xml_library_path_keys: ClassVar[set[str]] = {"Location", "Music Folder"}

    musicbee_folder: DirectoryPath = Field(
        description="The absolute path of the musicbee folder containing settings and library files.",
    )
    library_folders: Annotated[set[DirectoryPath], BeforeValidator(to_set)] = Field(
        description="Set of folders to scan for music files.",
        default_factory=set,
        init=False,
        frozen=True,
    )
    playlist_folder: Path = Field(
        description="Path to the folder containing the playlist. This may absolute or relative to the library folders.",
        default=Path("Playlists"),
    )

    @property
    def xml_settings_path(self) -> FilePath:
        """The path to the MusicBee settings file."""
        return self.musicbee_folder.joinpath(self._xml_settings_path)

    @property
    def xml_library_path(self) -> FilePath:
        """The path to the MusicBee library file."""
        return self.musicbee_folder.joinpath(self._xml_library_path)

    @model_validator(mode="before")
    @classmethod
    def _add_library_path[T](cls, data: T | MutableMapping[str, Any]) -> T | MutableMapping[str, Any]:
        if not isinstance(data, MutableMapping) or (key := "musicbee_folder") not in data:
            return data

        data["path"] = Path(data[key]).joinpath(cls._xml_library_path)
        return data

    @model_validator(mode="after")
    def _validate_settings_file_exists(self) -> Self:
        if not self.xml_settings_path.is_file():
            raise FileDoesNotExistError(self.xml_settings_path, "MusicBee settings file does not exist")
        return self

    @model_validator(mode="after")
    def _validate_library_file_exists(self) -> Self:
        if not self.xml_library_path.is_file():
            raise FileDoesNotExistError(self.xml_library_path, "MusicBee library file does not exist")
        return self

    @model_validator(mode="after")
    def _validate_playlists_folder_exists(self) -> Self:
        if self.playlist_folder.is_absolute():
            return self

        path = self.musicbee_folder.joinpath(self.playlist_folder)
        if path.is_dir():
            self.__dict__["playlist_folder"] = path

        return self

    async def load_settings_xml(self) -> dict[str, Any]:
        """Load the MusicBee library XML file from disk."""
        # TODO: make this async
        with self.xml_settings_path.open("r", encoding="utf-8") as file:
            #: A map representation of the loaded XML settings data
            settings: dict[str, Any] = xmltodict.parse(file.read())
        return settings["ApplicationSettings"]

    async def set_library_folders(self, xml: dict[str, Any] = None) -> None:
        """Set the library folders from the settings XML file."""
        if not xml:
            xml = await self.load_settings_xml()

        paths = self.path_mapper.map_many(to_set(xml.get("OrganisationMonitoredFolders", {}).get("string") or ()))
        self.library_folders.clear()
        self.library_folders.update(map(Path, paths))

    async def load_library_xml(self) -> dict[str, Any]:
        """Load the MusicBee library XML file from disk."""
        # TODO: make this async
        parser = XMLLibraryParser(source=self.xml_library_path, path_keys=self._xml_library_path_keys)
        return parser.parse()

    async def load_tracks(self) -> None:
        await self.set_library_folders()
        await super().load_tracks()

        track_xml_map = await self._map_track_to_xml()
        track_map = {track.path: track for track in self.tracks}
        for path, track_xml in track_xml_map.items():
            track = track_map[path]
            track.rating = int(track_xml.get("Rating")) if track_xml.get("Rating") is not None else None
            track.added_at = track_xml.get("Date Added")
            track.last_played_at = track_xml.get("Play Date UTC")
            track.play_count = track_xml.get("Play Count", 0)

        self._log_errors("Could not find a loaded track for these paths from the MusicBee library file")

    async def _map_track_to_xml(self, xml: dict[str, Any] = None) -> dict[Path, dict[str, Any]]:
        if xml is None:
            xml = await self.load_library_xml()

        # need to remove library folders to allow match to be os agnostic
        track_map = {
            str(track.path).removeprefix(str(folder)).casefold(): track
            for folder in self.library_folders for track in self.tracks
        }
        track_xml_map: dict[Path, dict[str, Any]] = {}

        for track_xml in xml["Tracks"].values():
            track = self._get_track_from_xml_path(
                track_xml=track_xml, track_map=track_map, library_folder=xml["Music Folder"]
            )
            if track is None:
                continue

            track_xml_map[track.path] = track_xml

        return track_xml_map

    def _get_track_from_xml_path(
            self,
            track_xml: dict[str, Any],
            track_map: dict[str, LocalTrack],
            library_folder: str,
    ) -> LocalTrack | None:
        if track_xml["Track Type"] != "File":
            return

        path = track_xml["Location"]
        prefixes = {*map(str, self.library_folders), library_folder}
        if isinstance(self.path_mapper, PathStemMapper):
            prefixes.update(self.path_mapper.stem_map.keys())

        for prefix in prefixes:
            if (track := track_map.get(path.removeprefix(prefix).casefold())) is not None:
                return track

        self.errors.append(path)

    async def save(self, dry_run: bool = True, *_, **__) -> dict[str, Any]:
        """
        Generate and save the XML library file for this MusicBee library.

        :param dry_run: Run function, but do not modify the file on the disk.
        """
        # TODO: make this async
        parser = XMLLibraryParser(source=self.xml_library_path, path_keys=self._xml_library_path_keys)
        xml = parser.parse()

        tracks, tracks_id_map = await self._tracks_to_xml(xml)
        playlists = await self._playlists_to_xml(xml, tracks=tracks_id_map)

        xml["Music Folder"] = str(self.musicbee_folder)
        xml["Tracks"] = dict(sorted(tracks.items(), key=lambda item: item[0]))
        xml["Playlists"] = sorted(playlists.values(), key=lambda pl_xml: pl_xml["Playlist ID"])

        if not dry_run:
            with self.xml_library_path.open("w", encoding="utf-8") as file:
                file.write(parser.unparse(xml))

        return xml

    async def _tracks_to_xml(self, xml: dict[str, Any]) -> tuple[dict[int, dict[str, Any]], dict[Path, int]]:
        tracks_xml = await self._map_track_to_xml(xml)
        track_id_map = {path: track_xml["Track ID"] for path, track_xml in tracks_xml.items()}
        track_persistent_id_map = {path: track_xml["Persistent ID"] for path, track_xml in tracks_xml.items()}

        self._log_errors("Could not find a loaded track for these paths from the MusicBee library file")

        tracks: dict[int, dict[str, Any]] = {}
        max_track_id = max(list(track_id_map.values())) if track_id_map else 0
        for track_id, track in enumerate(self.tracks, max(1, max_track_id + 1)):
            if track.path in track_id_map:
                track_id = track_id_map[track.path]
            persistent_id = track_persistent_id_map.get(track.path)
            track_xml = self._track_to_xml(track, track_id=track_id, persistent_id=persistent_id)

            tracks[track_id] = track_xml
            track_id_map[track.path] = track_id
            track_persistent_id_map[track.path] = persistent_id

        return tracks, track_id_map

    @classmethod
    def _track_to_xml(cls, track: LocalTrack, track_id: int, persistent_id: str | None = None) -> dict[str, Any]:
        genres = {}
        if track.genres and len(track.genres) == 1:
            genres = {"Genre": track.genres[0]}
        elif track.genres:
            genres = {f"Genre{i}": genre for i, genre in enumerate(track.genres, 1)}

        data = {
            "Track ID": track_id,
            "Persistent ID": cls._generate_persistent_id(persistent_id=persistent_id, value=track.path),
            "Name": track.name,
            "Artist": track.artist,
            "Album": track.album,
            "Album Artist": track.album.artist if track.album is not None else None,
            "Track Number": track.track.number if track.track is not None else None,
            "Track Count": track.track_total if track.track is not None else None,
        } | genres | {
            "Year": track.released_at.year if track.released_at is not None else None,
            "BPM": track.bpm,
            "Disc Number": track.disc.number if track.disc is not None else None,
            "Disc Count": track.disc.total if track.disc is not None else None,
            "Compilation": track.album.compilation if track.album is not None else None,
            "Comments": track.tag_sep.join(track.comments) if track.comments else None,
            "Total Time": int(track.length * 1000) if track.length is not None else None,  # in milliseconds
            "Rating": track.rating,
            # "Composer": track.composer,  # currently not supported by this program
            # "Conductor": track.conductor,  # currently not supported by this program
            # "Publisher": track.publisher,  # currently not supported by this program
            # "Encoder": track.encoder,  # currently not supported by this program
            "Size": track.size,
            "Kind": track.type,
            # "": track.channels,  # unknown MusicBee mapping
            "Bit Rate": int(track.bit_rate) if track.bit_rate is not None else None,
            # "": track.bit_depth if track.bit_depth is not None else None,  # unknown MusicBee mapping
            "Sample Rate": int(track.sample_rate * 1000) if track.sample_rate is not None else None,  # in Hz
            "Date Modified": track.modified_at,
            "Date Added": track.added_at,
            "Play Date UTC": track.last_played_at,
            "Play Count": track.play_count,
            "Track Type": "File",  # can also be 'URL' for streams
            "Location": str(track.path),
        }

        return dict(filter(lambda item: item[1] is not None, data.items()))

    async def _playlists_to_xml(self, xml: dict[str, Any], tracks: dict[Path, int]) -> dict[int, dict[str, Any]]:
        pl_id_map = {pl_xml["Name"]: pl_xml["Playlist ID"] for pl_xml in xml["Playlists"]}
        pl_persistent_id_map = {pl_xml["Name"]: pl_xml["Playlist Persistent ID"] for pl_xml in xml["Playlists"]}

        playlists: dict[int, dict[str, Any]] = {}
        max_playlist_id = max(list(pl_id_map.values())) if pl_id_map else 0
        for pl_id, pl in enumerate(self.playlists.unique, max_playlist_id + 1):
            if pl.name in pl_id_map:
                pl_id = pl_id_map[pl.name]
            persistent_id = pl_persistent_id_map.get(pl.name)
            playlists[pl_id] = self._playlist_to_xml(pl, tracks=tracks, playlist_id=pl_id, persistent_id=persistent_id)

        return playlists

    @classmethod
    def _playlist_to_xml(
            cls,
            playlist: LocalPlaylist,
            tracks: Mapping[Path, int],
            playlist_id: int,
            persistent_id: str | None = None,
    ) -> dict[str, Any]:
        data = {
            "Playlist ID": playlist_id,
            "Playlist Persistent ID": cls._generate_persistent_id(persistent_id=persistent_id, value=playlist.path),
            "All Items": True,  # don't know what this does, what happens if 'False'?
            "Name": playlist.name,
            "Description": playlist.description,
            "Playlist Items": [{"Track ID": track_id} for track_id in tracks],
        }

        return dict(filter(lambda item: item[1] is not None, data.items()))

    @staticmethod
    def _generate_persistent_id(value: str | Path | None = None, persistent_id: str | None = None) -> str:
        if not value and not persistent_id:
            raise MusifyTypeError(
                "You must provide either a persistent ID to validate or a value to generate a persistent ID from."
            )

        persistent_id = persistent_id or hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:16]
        if (length := len(persistent_id)) > 16:
            raise MusifyValueError(f"Persistent ID is >16-characters in length ({length=}): {persistent_id}")
        return persistent_id.upper()


# noinspection PyProtectedMember
class XMLLibraryParser(BaseModel):
    """Parses MusicBee XML files to and from iTunes style XML."""
    __required_modules__ = {"xmltodict": xmltodict, "etree": etree}

    _iterparse: etree.iterparse | None = PrivateAttr(default=None)

    source: str | Path = Field(
        description="The source of the XML data, typically the path to the XML file.",
    )
    path_keys: set[str] = Field(
        description="A list of keys in the XML file that need to be processed as system paths.",
        default_factory=set,
    )
    timestamp_format: str = Field(
        description="The string representation of the timestamp format when parsing.",
        default="%Y-%m-%dT%H:%M:%SZ",
    )

    def to_xml_timestamp(self, timestamp: datetime | None) -> str | None:
        """Convert timestamp string as found in the MusicBee XML library file to a ``datetime`` object"""
        if timestamp:
            return timestamp.strftime(self.timestamp_format)

    def from_xml_timestamp(self, timestamp_str: str | None) -> datetime | None:
        """Convert timestamp string as found in the MusicBee XML library file to a ``datetime`` object"""
        if timestamp_str:
            return datetime.strptime(timestamp_str, self.timestamp_format)

    @staticmethod
    def to_xml_path(path: str | Path) -> str:
        """Convert a standard system path to a file path as found in the MusicBee XML library file"""
        return f"file://localhost/{quote(str(path).replace('\\', '/'), safe=':/!(),;@[]+')}"\
            .replace("%26", "&#38;")\
            .replace("%27", "&#39;")

    @staticmethod
    def from_xml_path(path: str | Path) -> str:
        """Clean the file paths as found in the MusicBee XML library file to a standard system path"""
        return os.path.normpath(unquote(re.sub(r"^file:/+localhost/?", "", str(path))))

    ###########################################################################
    ## Parse
    ###########################################################################
    def _iter_elements(self) -> Iterator[Element]:
        if self._iterparse is None:
            self._iterparse = etree.iterparse(self.source)

        for event, element in self._iterparse:
            yield element

        self._iterparse = None

    def _parse_value(self, value: Any, tag: str, parent: str | None = None):
        if tag == 'string':
            if parent in self.path_keys:
                return self.from_xml_path(value)
            else:
                return value
        elif tag == 'integer':
            try:
                return int(value) if "." not in value else float(value)
            except ValueError:
                return value
        elif tag == 'date':
            return self.from_xml_timestamp(value)
        elif tag in ['true', 'false']:
            return tag == 'true'

    def _parse_element(self, element: Element | None = None) -> Any:
        elem = next(self._iter_elements())
        peek = element.getnext() if element is not None else None

        if elem.tag in ['string', 'integer', 'date', 'true', 'false']:
            return self._parse_value(
                value=elem.text, tag=elem.tag, parent=element.text if element is not None else None
            )
        elif peek is not None and peek.tag == "dict":
            next_elem = next(self._iter_elements())
            value = self._parse_value(value=next_elem.text, tag=next_elem.tag, parent=elem.text)
            return {elem.text: value} | self._parse_dict()
        elif peek is not None and peek.tag == "array":
            return self._parse_array(elem)
        elif peek is not None:
            raise XMLReaderError(
                self.source, f"Unrecognised element: {element.tag}, {element.text}, {peek.tag}, {peek.text}"
            )
        elif element is not None:
            raise XMLReaderError(
                self.source, f"Unrecognised element: {element.tag}, {element.text}"
            )
        else:
            raise XMLReaderError(
                self.source, f"Unrecognised element: {elem.tag}, {elem.text}"
            )

    def _parse_array(self, element: Element | None = None) -> list[Any]:
        array = []

        if element is not None and element.tag == "array" and element.text is None:
            return array  # array is empty, skip processing

        for elem in self._iter_elements():
            if elem is None or elem.tag == "array":
                break

            peek = elem.getnext()
            if elem.tag == "key":
                next_elem = next(self._iter_elements())
                value = self._parse_value(value=next_elem.text, tag=next_elem.tag, parent=elem.text)
                array.append({elem.text: value} | self._parse_dict())
            elif peek is None and element is not None:
                value = self._parse_value(value=elem.text, tag=elem.tag, parent=element.text)
                array.append({element.text: value} | self._parse_dict())
            elif elem.tag != "plist":
                array.append(self._parse_element(elem))

        return array

    def _parse_dict(self) -> dict[str, Any]:
        record = {}

        for elem in self._iter_elements():
            if elem is None or elem.tag == "dict":
                break

            peek = elem.getnext()
            if peek is not None and peek.tag == "dict":
                record[elem.text] = self._parse_dict()
            else:
                record[elem.text] = self._parse_element(elem)

        return record

    def parse(self) -> dict[str, Any]:
        """Parse the XML file from the currently stored ``path`` to a dictionary"""
        try:
            et = etree.parse(self.source)
        except OSError:
            et = etree.fromstring(self.source)

        root_name = et.docinfo.root_name
        results = {}

        for element in self._iter_elements():
            peek = element.getnext()
            if peek is None:
                break

            if element.tag == root_name:
                continue
            elif element.tag == "key":
                key = element.text
                if peek.tag == "dict":
                    results[key] = self._parse_dict()
                elif peek.tag == "array":
                    results[key] = self._parse_array()
                else:
                    results[key] = self._parse_element(element)
            else:
                raise NotImplementedError

        # close the iterator
        for _ in self._iterparse:
            pass
        self._iterparse = None

        return results

    ###########################################################################
    ## Unparse
    ###########################################################################
    def _unparse_dict(self, element: Element, data: Mapping[str, Any]):
        sub_element: Element = etree.SubElement(element, "dict")
        for key, value in data.items():
            etree.SubElement(sub_element, "key").text = str(key)

            if isinstance(value, bool):
                etree.SubElement(sub_element, str(value).lower())
            elif isinstance(value, str | Path):
                value = str(value)
                if key in self.path_keys:
                    etree.SubElement(sub_element, "string").text = self.to_xml_path(value)
                else:
                    etree.SubElement(sub_element, "string").text = str(value)
            elif isinstance(value, Number):
                etree.SubElement(sub_element, "integer").text = str(value)
            elif isinstance(value, datetime):
                etree.SubElement(sub_element, "date").text = self.to_xml_timestamp(value)
            elif isinstance(value, Mapping):
                self._unparse_dict(element=sub_element, data=value)
            elif isinstance(value, Sequence):
                array_element: etree.Element = etree.SubElement(sub_element, "array")
                for item in value:
                    self._unparse_dict(element=array_element, data=item)
            else:
                raise XMLReaderError(
                    self.source, f"Unexpected value type: {value} ({type(value).__name__})"
                )

    def unparse(self, data: Mapping[str, Any]) -> str:
        """Un-parse a map of XML ``data`` to XML and save to file."""
        try:
            et = etree.parse(self.source)
        except XMLReaderError:
            et = etree.fromstring(self.source)

        parsed: dict[str, Any] = xmltodict.parse(etree.tostring(et.getroot(), encoding='utf-8', method='xml'))

        # noinspection PyAbstractClass
        root: etree.Element = etree.Element(et.docinfo.root_name)
        # noinspection PyUnresolvedReferences
        root.set("version", parsed[et.docinfo.root_name]["@version"])

        self._unparse_dict(element=root, data=data)
        etree.indent(root, space="\t", level=0)

        # convert to string and apply formatting to ensure output string is expected format
        output: str = etree.tostring(
            root, xml_declaration=True, encoding=et.docinfo.encoding, doctype=et.docinfo.doctype
        ).decode(et.docinfo.encoding)
        output = re.sub(r"</key>\n\s+<(string|integer|date|true|false)", r"</key><\1", output)
        output = re.sub("\n\t", "\n", output)
        output = output.replace("'", '"')
        output = output.rstrip('\n') + '\n'

        return output
