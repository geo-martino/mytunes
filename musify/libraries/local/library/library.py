"""
The core, basic library implementation which is just a simple set of folders.
"""
import functools
import itertools
import os
from collections.abc import Collection, Mapping, Iterable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from aiorequestful.types import UnitCollection, UnitIterable

from musify.base import Result
from musify.exception import MusifyError
from musify.file.path_mapper import PathMapper, PathStemMapper
from musify.libraries.core.object import Library, LibraryMergeType
from musify.libraries.local.collection import LocalCollection, LocalFolder, LocalAlbum, LocalArtist, LocalGenres
from musify.libraries.local.playlist import PLAYLIST_CLASSES, LocalPlaylist, load_playlist
from musify.libraries.local.track import TRACK_CLASSES, LocalTrack, load_track
from musify.libraries.local.track.field import LocalTrackField
from musify.libraries.remote.core.wrangle import RemoteDataWrangler
from musify.logger import STAT
from musify.processors.base import Filter
from musify.processors.filter import FilterDefinedList
from musify.processors.sort import ItemSorter
from musify.utils import align_string, get_max_width, to_collection, classproperty

type RestoreTracksType = Iterable[Mapping[str, Any]] | Mapping[str | Path, Mapping[str, Any]]


class LocalLibrary(LocalCollection[LocalTrack], Library[LocalTrack]):
    """
    Represents a local library, providing various methods for manipulating
    tracks and playlists across an entire local library collection.

    :param library_folders: The absolute paths of the library folders containing all tracks.
        The intialiser will check for the existence of these paths and only store them if they exist.
    :param playlist_folder: The absolute path of the playlist folder containing all playlists
        or the relative path within one of the available ``library_folders``.
        If a relative path is given and many library folders are given,
        only the first path that gives an existing result is processed.
        The setter will check for the existence of this path and only store the absolute path if it exists.
    :param playlist_filter: An optional :py:class:`Filter` to apply or collection of playlist names to include when
        loading playlists. Playlist names will be passed to this filter to limit which playlists are loaded.
    :param path_mapper: Optionally, provide a :py:class:`PathMapper` for paths stored in the playlist files.
        Useful if the playlist files contain relative paths and/or paths for other systems that need to be
        mapped to absolute, system-specific paths to be loaded and back again when saved.
    :param remote_wrangler: Optionally, provide a :py:class:`RemoteDataWrangler` object for processing URIs on tracks.
        If given, the wrangler can be used when calling __get_item__ to get an item from the collection from its URI.
        The wrangler is also used when loading tracks to allow them to process URI tags.
        For more info on this, see :py:class:`LocalTrack`.
    :param name: A name to assign to this library.
    """

    __slots__ = (
        "_name",
        "_library_folders",
        "_playlist_folder",
        "playlist_filter",
        "path_mapper",
        "_playlist_paths",
        "_playlists",
        "_track_paths",
        "_tracks",
        "errors",
    )
    __attributes_classes__ = (Library, LocalCollection)
    __attributes_ignore__ = ("tracks_in_playlists",)

    @property
    def name(self) -> str:
        return self._name

    @name.setter
    def name(self, value: str):
        self._name = value

    # noinspection PyMethodParameters
    @classproperty
    def source(cls) -> str:
        """The type of local library loaded"""
        return cls.__name__.replace("Library", "")

    @property
    def tracks(self) -> list[LocalTrack]:
        """The tracks in this collection"""
        return self._tracks

    @property
    def playlists(self) -> dict[str, LocalPlaylist]:
        """The playlists in this library mapped as ``{<name>: <playlist>}``"""
        return self._playlists

    @property
    def library_folders(self) -> list[Path]:
        """Path to the library folder"""
        return self._library_folders

    @library_folders.setter
    def library_folders(self, folders: UnitCollection[str | Path] | None):
        """
        Sets the library folder path and generates a set of available and valid track paths in the folder.
        Skips settings if the given value is None.
        """
        if folders is None:
            return

        self._library_folders: list[Path] = [folder for folder in map(Path, to_collection(folders)) if folder.exists()]

        self._track_paths = {
            path for folder in self._library_folders for cls in TRACK_CLASSES for path in cls.get_filepaths(folder)
        }
        if isinstance(self.path_mapper, PathStemMapper):
            self.path_mapper.available_paths = self._track_paths

        self.logger.debug(
            f"Set library folder(s): {", ".join(map(str, self.library_folders))} | "
            f"{len(self._track_paths)} track paths found"
        )

    @property
    def playlist_folder(self) -> Path:
        """Path to the playlist folder"""
        return self._playlist_folder

    @playlist_folder.setter
    def playlist_folder(self, folder: str | Path | None):
        """
        Sets the playlist folder path and generates a set of available and valid playlists in the folder.
        Appends the library folder path if the given path is not valid. Skips settings if the given value is None.
        """
        if folder is None:
            return

        folder = Path(folder)
        if (not folder.is_dir() or not folder.is_absolute()) and self.library_folders:
            for fldr in self.library_folders:
                value = fldr.joinpath(folder)
                if value.is_dir():
                    folder = value
                    break
        if not folder.is_dir():
            return

        self._playlist_folder = folder
        self._playlist_paths = None

        playlists = {
            Path(str(path).removeprefix(str(self._playlist_folder))).stem: path
            for cls in PLAYLIST_CLASSES for path in cls.get_filepaths(self._playlist_folder)
        }

        pl_total = len(playlists)
        pl_filtered = self.playlist_filter(playlists)
        self._playlist_paths = {
            name: path for name, path in sorted(playlists.items(), key=lambda x: x[0].casefold())
            if name in pl_filtered
        }

        self.logger.debug(f"Set playlist folder: {self.playlist_folder} | " + (
            f"Filtered out {pl_total - len(self._playlist_paths)} playlists "
            f"from {pl_total} {self.name} available playlists"
            if (pl_total - len(pl_filtered)) > 0 else f"{len(self._playlist_paths)} playlists found"
        ))

    @property
    def folders(self) -> list[LocalFolder]:
        """
        Dynamically generate a set of folder collections from the tracks in this library.
        Folder collections are generated relevant to the library folder it is found in.
        """
        def get_relative_path(track: LocalTrack) -> Path:
            """Return path of a track relative to the library folders of this library"""
            path = functools.reduce(
                lambda p, f: str(p).replace(str(f), ""), self.library_folders, str(track.path)
            )
            return Path(path.lstrip(os.path.sep)).parent

        def create_folder_collection(path: Path, tracks: Collection[LocalTrack]) -> LocalFolder:
            """
            Create a :py:class:`LocalFolder` collection from the given ``tracks``,
            ensuring the collection has the exact given ``name``.

            The LocalFolder filters the input tracks by the given name,
            where it will match on ``track.folder`` == ``name``.
            Given that ``track.folder`` is just the direct parent folder stem only,
            We need to supply this stem folder on init and assign the full folder path back after.
            """
            folder = LocalFolder(tracks=tracks, name=path.name, remote_wrangler=self.remote_wrangler)
            folder._name = str(path)
            return folder

        grouped = itertools.groupby(sorted(self.tracks, key=lambda track: track.path), get_relative_path)
        collections = [create_folder_collection(path=path, tracks=list(group)) for path, group in grouped]
        return sorted(collections, key=lambda x: x.name)

    @property
    def albums(self) -> list[LocalAlbum]:
        """Dynamically generate a set of album collections from the tracks in this library"""
        grouped = ItemSorter.group_by_field(items=self.tracks, field=LocalTrackField.ALBUM)
        collections = [
            LocalAlbum(tracks=group, name=name, remote_wrangler=self.remote_wrangler)
            for name, group in grouped.items() if name
        ]
        return sorted(collections, key=lambda x: x.name)

    @property
    def artists(self) -> list[LocalArtist]:
        """Dynamically generate a set of artist collections from the tracks in this library"""
        grouped = ItemSorter.group_by_field(items=self.tracks, field=LocalTrackField.ARTISTS)
        collections = [
            LocalArtist(tracks=group, name=name, remote_wrangler=self.remote_wrangler)
            for name, group in grouped.items() if name
        ]
        return sorted(collections, key=lambda x: x.name)

    @property
    def genres(self) -> list[LocalGenres]:
        """Dynamically generate a set of genre collections from the tracks in this library"""
        grouped = ItemSorter.group_by_field(items=self.tracks, field=LocalTrackField.GENRES)
        collections = [
            LocalGenres(tracks=group, name=name, remote_wrangler=self.remote_wrangler)
            for name, group in grouped.items() if name
        ]
        return sorted(collections, key=lambda x: x.name)

    def __init__(
            self,
            library_folders: UnitCollection[str | Path] | None = None,
            playlist_folder: str | Path | None = None,
            playlist_filter: Collection[str] | Filter[str] = (),
            path_mapper: PathMapper = PathMapper(),
            remote_wrangler: RemoteDataWrangler | None = None,
            name: str = None,
    ):
        super().__init__(remote_wrangler=remote_wrangler)

        self._name: str = name if name else self.source

        self.logger.debug(f"Setup {self.name} library: START")
        self.logger.info(f"\33[1;95m ->\33[1;97m Setting up {self.name} library \33[0m")
        self.logger.print_line()

        #: Passed to playlist objects when loading playlists to map paths stored in the playlist file.
        self.path_mapper = path_mapper

        self._library_folders: list[Path] = []
        self._track_paths: set[Path] = set()
        self.library_folders = library_folders

        if not isinstance(playlist_filter, Filter):
            playlist_filter = FilterDefinedList(playlist_filter)
        #: :py:class:`Filter` to filter out the playlists loaded by name.
        self.playlist_filter: Filter[str] = playlist_filter

        self._playlist_folder: Path | None = None
        # playlist lowercase name mapped to its filepath for all accepted filetypes in playlist folder
        self._playlist_paths: dict[str, Path] = {}
        self.playlist_folder = playlist_folder

        self._tracks: list[LocalTrack] = []
        self._playlists: dict[str, LocalPlaylist] = {}

        #: Stores the paths that caused errors when loading/enriching
        self.errors: list[str] = []
        self.logger.debug(f"Setup {self.name} library: DONE\n")

    async def load(self) -> None:
        """Loads all tracks and playlists in this library from scratch and log results."""
        self.logger.debug(f"Load {self.name} library: START")
        self.logger.info(
            f"\33[1;95m ->\33[1;97m Loading {self.name} library of "
            f"{len(self._track_paths)} tracks and {len(self._playlist_paths)} playlists \33[0m"
        )

        await self.load_tracks()
        await self.load_playlists()

        self.logger.print_line(STAT)
        self.log_tracks()
        self.log_playlists()

        self.logger.print_line()
        self.logger.debug(f"Load {self.name} library: DONE\n")

    def _log_errors(self, message: str = "Could not load") -> None:
        """Log paths which had some error while loading"""
        errors = tuple(f"\33[91m{e}\33[0m" for e in sorted(self.errors))
        if len(errors) > 0:
            self.logger.warning(f"\33[97m{message}: \33[0m\n\t- {"\n\t- ".join(errors)} ")
            self.logger.print_line()
        self.errors.clear()

    ###########################################################################
    ## Tracks
    ###########################################################################
    async def load_track(self, path: str | Path) -> LocalTrack | None:
        """
        Wrapper for :py:func:`load_track` which automatically loads the track at the given ``path``
        and assigns optional arguments using this library's attributes.

        Handles exceptions by logging paths which produce errors to internal list of ``errors``.
        """
        try:
            return await load_track(path=path, remote_wrangler=self.remote_wrangler)
        except MusifyError as ex:
            self.logger.debug(f"Load error for track: {path} - {ex}")
            self.errors.append(path)

    async def load_tracks(self) -> None:
        """Load all tracks from all the valid paths in this library, replacing currently loaded tracks."""
        if not self._track_paths:
            return

        self.logger.debug(f"Load {self.name} tracks: START")
        self.logger.info(
            f"\33[1;95m  >\33[1;97m Extracting metadata and properties for {len(self._track_paths)} tracks \33[0m"
        )

        # WARNING: making this run asynchronously will break tqdm; bar will get stuck after 1-2 ticks
        bar = self.logger.get_synchronous_iterator(
            self._track_paths,
            desc="Loading tracks",
            unit="tracks",
            total=len(self._track_paths)
        )
        tracks = [await self.load_track(path) for path in bar]
        self._tracks = [track for track in tracks if track is not None]

        self._log_errors("Could not load the following tracks")
        self.logger.debug(f"Load {self.name} tracks: DONE\n")

    def log_tracks(self) -> None:
        width = get_max_width(self._playlist_paths) if self._playlist_paths else 20
        self.logger.stat(
            f"\33[1;96m{'LIBRARY URIS':<{width}}\33[1;0m |"
            f"\33[92m{sum([track.has_uri is True for track in self.tracks]):>6} available \33[0m|"
            f"\33[91m{sum([track.has_uri is None for track in self.tracks]):>6} missing \33[0m|"
            f"\33[93m{sum([track.has_uri is False for track in self.tracks]):>6} unavailable \33[0m|"
            f"\33[1;94m{len(self.tracks):>6} total \33[0m"
        )

    ###########################################################################
    ## Playlists
    ###########################################################################
    async def load_playlist(self, path: str | Path) -> LocalPlaylist:
        """
        Wrapper for :py:func:`load_playlist` which automatically loads the playlist at the given ``path``
        and assigns optional arguments using this library's attributes.

        Handles exceptions by logging paths which produce errors to internal list of ``errors``.
        """
        try:
            return await load_playlist(
                path=path, tracks=self.tracks, path_mapper=self.path_mapper, remote_wrangler=self.remote_wrangler,
            )
        except MusifyError as ex:
            self.logger.debug(f"Load error for playlist: {path} - {ex}")
            self.errors.append(path)

    async def load_playlists(self) -> None:
        """
        Load all playlists found in this library's ``playlist_folder``,
        filtered down using the ``playlist_filter`` if given, replacing currently loaded playlists.

        :return: The loaded playlists.
        :raise LocalCollectionError: If a given playlist name cannot be found.
        """
        if not self._playlist_paths:
            return

        self.logger.debug(f"Load {self.name} playlist data: START")
        self.logger.info(
            f"\33[1;95m  >\33[1;97m Loading playlist data for {len(self._playlist_paths)} playlists \33[0m"
        )

        # WARNING: making this run asynchronously will break tqdm; bar will get stuck after 1-2 ticks
        bar = self.logger.get_synchronous_iterator(
            self._playlist_paths.values(),
            desc="Loading playlists",
            unit="playlists",
            total=len(self._playlist_paths)
        )
        self._playlists = {
            pl.name: pl for pl in sorted([await self.load_playlist(pl) for pl in bar], key=lambda x: x.name.casefold())
        }

        self._log_errors("Could not load the following playlists")
        self.logger.debug(f"Load {self.name} playlists: DONE\n")

    def log_playlists(self) -> None:
        max_width = get_max_width(self.playlists)

        self.logger.stat(f"\33[1;96m{self.name.upper()} PLAYLISTS: \33[0m")
        for name, playlist in self.playlists.items():
            self.logger.stat(
                f"\33[97m{align_string(name, max_width=max_width)} \33[0m|"
                f"\33[92m{sum(1 for t in playlist if t.has_uri):>6} available \33[0m|"
                f"\33[91m{sum(1 for t in playlist if t.has_uri is None):>6} missing \33[0m|"
                f"\33[93m{sum(1 for t in playlist if t.has_uri is False):>6} unavailable \33[0m|"
                f"\33[1;94m{len(playlist):>6} total \33[0m"
            )

    async def save_playlists(self, dry_run: bool = True) -> dict[LocalPlaylist, Result]:
        """
        For each Playlist in this Library, saves its associate tracks and its settings (if applicable) to file.

        :param dry_run: Run function, but do not modify the file on the disk.
        :return: A map of the playlist name to the results of its sync as a :py:class:`Result` object.
        """
        async def _save_playlist(pl: LocalPlaylist) -> tuple[LocalPlaylist, Result]:
            return pl, await pl.save(dry_run=dry_run)

        # WARNING: making this run asynchronously will break tqdm; bar will get stuck after 1-2 ticks
        bar = self.logger.get_synchronous_iterator(
            self.playlists.values(), desc="Updating playlists", unit="tracks"
        )
        return dict([await _save_playlist(pl) for pl in bar])

    def merge_playlists(
            self, playlists: LibraryMergeType[LocalTrack], reference: LibraryMergeType[LocalTrack] | None = None
    ) -> None:
        current_names = set(self.playlists)

        super().merge_playlists(playlists=playlists, reference=reference)

        for pl in self.playlists.values():
            if pl.name in current_names:
                continue

            if isinstance(playlists, LocalLibrary):
                rel_path = pl.path.relative_to(playlists.playlist_folder)
            else:
                rel_path = pl.path.name

            pl.path = self.playlist_folder.joinpath(rel_path)

    ###########################################################################
    ## Backup/restore
    ###########################################################################
    def restore_tracks(
            self, backup: RestoreTracksType, tags: UnitIterable[LocalTrackField] = LocalTrackField.ALL
    ) -> int:
        """
        Restore track tags from a backup to loaded track objects. This does not save the updated tags.

        :param backup: Backup data in the form ``{<path>: {<Map of JSON formatted track data>}}``
        :param tags: Set of tags to restore.
        :return: The number of tracks restored
        """
        backup = self._extract_tracks_from_backup(backup)
        tag_names = set(LocalTrackField.to_tags(tags))

        count = 0
        for track in self.tracks:
            track_map = backup.get(track.path)
            if not track_map:
                continue

            for tag in tag_names:
                if tag in track_map:
                    track[tag] = track_map[tag]
            count += 1

        return count

    @staticmethod
    def _extract_tracks_from_backup(backup: RestoreTracksType) -> dict[Path, Mapping[str, Any]]:
        if isinstance(backup, Mapping):
            backup = {Path(path): track_map for path, track_map in backup.items()}
        else:
            backup = {Path(track_map["path"]): track_map for track_map in backup}
        return backup

    def _get_attributes(self) -> dict[str, Any]:
        attributes_extra = {"remote_source": self.remote_wrangler.source if self.remote_wrangler else None}
        return super()._get_attributes() | attributes_extra

    def json(self):
        self.logger.info(
            f"\33[1;95m ->\33[1;97m Extracting JSON data for library of "
            f"{len(self.tracks)} tracks and {len(self.playlists)} playlists\n"
        )

        attributes = self._get_attributes()

        playlists: dict[str, LocalPlaylist] | None = None
        if "playlists" in attributes and "tracks" in attributes:
            playlists = attributes["playlists"]
            attributes["playlists"] = {}

        self_json = self._to_json(attributes, pool=True)

        if playlists is not None:
            tracks: Mapping[str, Mapping[str, Any]] = {track["path"]: track for track in self_json["tracks"]}

            def _get_playlist_json(pl: LocalPlaylist) -> tuple[str, dict[str, Any]]:
                pl_attributes = pl._get_attributes()
                pl_attributes["tracks"] = []

                pl_json = pl._to_json(pl_attributes, pool=True)
                pl_json["tracks"] = [tracks.get(str(track.path), str(track.path)) for track in pl]

                return pl.name, pl_json

            with ThreadPoolExecutor(thread_name_prefix="to-json-playlists") as executor:
                tasks = executor.map(_get_playlist_json, playlists.values())

            self_json["playlists"] = dict(sorted(tasks, key=lambda x: x[0]))

        return self_json
