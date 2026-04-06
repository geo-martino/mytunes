import itertools
from collections.abc import Generator, Iterable, Collection
from pathlib import Path
from typing import Annotated, ClassVar, final

import tabulate
from mutagen import MutagenError
from pydantic import Field, field_validator, DirectoryPath, PrivateAttr
from termcolor import colored

from musify._types import TO_SET, to_set
from musify.exception import MusifyError, MusifyValueError
from musify.local._collection._base import LocalCollection
from musify.local._collection.album import LocalAlbumCollection
from musify.local._collection.artist import LocalArtistCollection
from musify.local._collection.folder import Folder
from musify.local._collection.genre import LocalGenreCollection
from musify.local._collection.playlist import LocalPlaylist, LOCAL_PLAYLIST_ADAPTER
from musify.local._collection.playlist.result import LoadPlaylistResult
from musify.logger import STAT
from musify.processors.filters import Filter
from musify.processors.filters.values import ValueFilter
from musify.processors.sort import ItemSorter
from .result import LibraryURIsResult
from ..._item.track import LocalTrack, HasLocalTracks, TagContext, LOCAL_TRACK_ADAPTER
from ...._models.collection.library import MutableLibrary
from ...._models.properties.file import PathMapper
from ...._models.properties.uri import URI
from ...._models.result import Result


@final
class LocalLibrary(
    HasLocalTracks[URI, LocalTrack],
    MutableLibrary[URI, LocalTrack, URI | Path, LocalPlaylist],
    LocalCollection[LocalTrack],
):
    """
    Represents a local library, providing various methods for manipulating
    tracks and playlists across an entire local library collection.
    """
    __final__ = True

    _ignore_folders: ClassVar[frozenset[str]] = frozenset({"$RECYCLE.BIN"})
    source: ClassVar[str] = "local"

    library_folders: Annotated[set[DirectoryPath], TO_SET] = Field(
        description="Set of folders to scan for music files.",
        default_factory=set,
    )
    playlist_folder: Path | None = Field(
        description="Path to the folder containing the playlist. This may absolute or relative to the library folders.",
        default=None,
    )
    path_mapper: PathMapper = Field(
        description="Mapper to use when mapping paths stored in the playlist files.",
        default_factory=PathMapper,
    )
    tracks_load_settings: TagContext = Field(
        description="Settings to apply when loading tracks in this library.",
        default_factory=TagContext,
        validation_alias="tracks_load_context",
    )

    _errors: list[str] = PrivateAttr(
        default_factory=list
    )

    @property
    def errors(self) -> list[str]:
        """List of errors encountered while loading the library."""
        return self._errors

    @field_validator("playlist_filter", mode="before", check_fields=True)
    @staticmethod
    def _convert_playlist_names_to_filter[T: str | Iterable[str]](names: T) -> T | ValueFilter[str]:
        if not names or isinstance(names, Filter):
            return names

        names = to_set(names)
        return ValueFilter(values=names)

    async def load(self) -> None:
        self.logger.info(f"Loading tracks and playlists in {self.source} library", header=1)

        with self.logger:
            await self.load_tracks()
            playlist_results = await self.load_playlists()

        self._log_load_playlists(playlist_results)
        self.logger.print_line(STAT)

        header = f"{self.source.upper()} TRACK AND PLAYLIST URIS"
        results: dict[str, LibraryURIsResult | None] = self._generate_playlist_uris_results()
        results[tabulate.SEPARATING_LINE] = None
        results["TRACKS"] = self._generate_track_uris_results()
        table = LibraryURIsResult.generate_table(results=results, header=header)

        self.logger.stat(table)
        self.logger.print_line(STAT)

    def _log_errors(self, message: str = "Could not load") -> None:
        if len(self.errors) == 0:
            return

        header = colored(message, "white") + ":"
        errors = list(map(lambda e: colored(e, "red"), sorted(set(self.errors))))

        log = "\n\t- ".join([header] + errors)
        self.logger.warning(log)
        self.logger.print_line()
        self.errors.clear()

    ###########################################################################
    ## Tracks
    ###########################################################################
    async def load_track(self, path: str | Path) -> LocalTrack | None:
        """
        Loads the track at the given ``path``.

        Handles exceptions by logging paths which produce errors to internal list of ``errors``.
        """
        try:
            async with self.concurrency:
                self.logger.debug(f"Loading track: {path}")
                file = await LocalTrack.load_file(path)

            return LOCAL_TRACK_ADAPTER.validate_python(file, context=self.tracks_load_settings)

        except (MusifyError, MutagenError, ValueError, OSError) as ex:
            self.logger.debug(f"Load error for track: {path} - {ex}")
            self.errors.append(path)

    async def load_tracks(self) -> int:
        if not (paths := set(self._track_paths)):
            return 0

        self.logger.info(f"Loading {len(paths)} tracks in {self.source} library", header=2)

        task_id = self.logger.progress.add_task(
            description=f"Loading {self.source} tracks", total=len(paths)
        )
        tracks = await self.logger.run_tasks_async(map(self.load_track, paths), task_id=task_id)
        self.tracks.replace(tracks)

        self._log_errors("Could not load the following tracks")
        return len(self.tracks)

    @property
    def _track_paths(self) -> Generator[Path, None, None]:
        if not self.library_folders:
            return

        extensions: set[str] = LocalTrack.supported_extensions

        folders = self.library_folders
        folder_message = "folder" if len(folders) == 1 else "folders"
        message = f"Scanning {len(folders)} {self.source} library {folder_message} for tracks with extensions:"
        self.logger.info(message, header=2, hidden=self.logger.format_list_to_string(extensions))

        for folder in folders:
            for path in folder.rglob(f"[!.]*"):
                if path.suffix.lstrip(".").casefold() not in extensions:
                    continue
                if any(part in path.parts for part in self._ignore_folders):
                    continue

                yield path

    def log_tracks(self) -> None:
        result = self._generate_track_uris_results()
        key = f"{self.source.upper()} TRACK URIS"
        table = result.generate_table(results={key: result})

        self.logger.stat(table)

    def _generate_track_uris_results(self) -> LibraryURIsResult[LocalTrack]:
        source = self.tracks_load_settings.remote_source
        return LibraryURIsResult.from_tracks(self.tracks, source=source)

    ###########################################################################
    ## Playlists
    ###########################################################################
    async def load_playlist(self, path: str | Path) -> tuple[LocalPlaylist, LoadPlaylistResult] | None:
        """
        Loads the playlist at the given ``path`` and assigns optional arguments using this library's attributes.

        Handles exceptions by logging paths which produce errors to internal list of ``errors``.
        """
        try:
            async with self.concurrency:
                self.logger.debug(f"Loading playlist: {path}")

                playlist = LOCAL_PLAYLIST_ADAPTER.validate_python(path)
                playlist.path_mapper = self.path_mapper

                result = await playlist.load(self.tracks)
                return playlist, result

        except (MusifyError, ValueError, FileNotFoundError) as ex:
            self.logger.debug(f"Load error for playlist: {path} - {ex}")
            self.errors.append(path)

    async def load_playlists(self) -> dict[str, LoadPlaylistResult]:
        if not (paths := set(self._playlist_paths)):
            return {}

        self.logger.info(f"Loading {len(paths)} playlists in {self.source} library", header=2)

        task_id = self.logger.progress.add_task(
            description=f"Loading {self.source} playlists", total=len(paths)
        )
        task = self.logger.run_tasks_async(map(self.load_playlist, paths), task_id=task_id)

        playlists: list[LocalPlaylist] = []
        results: dict[str, LoadPlaylistResult] = {}
        for playlist, result in await task:
            playlists.append(playlist)
            results[playlist.name] = result

        playlists = sorted(playlists, key=lambda x: x.name.casefold())
        results = dict(sorted(results.items(), key=lambda x: x[0].casefold()))
        self.playlists.replace(playlists)

        self._log_errors("Could not load the following playlists")
        return results

    @property
    def _playlist_paths(self) -> Generator[Path, None, None]:
        if self.playlist_folder is None:
            return

        if self.playlist_folder.is_absolute():
            folders = {self.playlist_folder}
        else:
            folders = {
                library_folder.joinpath(self.playlist_folder)
                for library_folder in self.library_folders
            }
            folders = {folder for folder in folders if folder.is_dir()}

        extensions: set[str] = LocalPlaylist.supported_extensions

        folder_message = "folder" if len(folders) == 1 else "folders"
        message = f"Scanning {len(folders)} {self.source} library {folder_message} for playlists with extensions:"
        self.logger.info(message, header=2, hidden=self.logger.format_list_to_string(extensions))

        total = 0
        filtered = 0
        for folder in folders:
            for path in folder.rglob(f"[!.]*"):
                if path.suffix.lstrip(".").casefold() not in extensions:
                    continue
                if any(part in path.parts for part in self._ignore_folders):
                    continue
                if self.playlist_filter and not self.playlist_filter.check(path.stem):
                    filtered += 1
                    continue

                total += 1
                yield path

        self.logger.debug(f"Filtered out {filtered} playlists from {total} {self.source} available playlists")

    def log_playlists(self, results: dict[str, LoadPlaylistResult] = None) -> None:
        if results:
            self._log_load_playlists(results)
        self._log_playlist_uris()

    def _log_load_playlists(self, results: dict[str, LoadPlaylistResult]) -> None:
        header = f"{self.source.upper()} PLAYLISTS LOADED"
        table = LoadPlaylistResult.generate_table(results=results, header=header)

        self.logger.stat(table)

    def _log_playlist_uris(self) -> None:
        results = self._generate_playlist_uris_results()
        header = f"{self.source.upper()} PLAYLIST URIS"
        table = LibraryURIsResult.generate_table(results=results, header=header)

        self.logger.stat(table)

    def _generate_playlist_uris_results(self) -> dict[str, LibraryURIsResult[LocalTrack]]:
        source = self.tracks_load_settings.remote_source
        return {
            playlist.name: LibraryURIsResult.from_tracks(playlist.tracks, source=source)
            for playlist in self.playlists.unique
        }

    async def save_playlists(self, dry_run: bool = True) -> dict[str, Result]:
        """
        Save associated tracks and settings (if applicable) for all playlists in this library.

        :param dry_run: Run function, but do not modify the file on the disk.
        :return: A map of the playlist name to the results of its sync as a :py:class:`Result` object.
        """
        async def _save_playlist(pl: LocalPlaylist) -> tuple[str, Result]:
            async with self.concurrency:
                return pl.name, await pl.save(dry_run=dry_run)

        self.logger.info(f"Saving {self.playlists.count} playlists in {self.source} {self.type}", header=2)

        task_id = self.logger.progress.add_task(description=f"Updating {self.source} playlists", total=self.playlists.count)
        results = await self.logger.run_tasks_async(map(_save_playlist, self.playlists.unique), task_id=task_id)
        return dict(results)

    ###########################################################################
    ## Collections
    ###########################################################################
    def folders(self, tracks: Collection[LocalTrack] = None) -> Generator[Folder, None, None]:
        """
        Dynamically generate a set of folder collections from the tracks in this library.
        Folder collections are generated relevant to the library folder it is found in.
        """
        if tracks is None:
            tracks = self.tracks

        def get_relative_path(track: LocalTrack) -> Path:
            """Return path of a track relative to the library folders of this library"""
            for folder in self.library_folders:
                if track.path.is_relative_to(folder):
                    return track.path.relative_to(folder).parent

            raise MusifyValueError(f"Track path is not relative to any library folders: {track.path}")

        groups = itertools.groupby(sorted(tracks, key=get_relative_path), get_relative_path)
        for path, group in groups:
            if not path.name:
                continue

            group = sorted(group, key=lambda track: track.filename)
            yield Folder(name=path.name, tracks=group)

    def albums(self, tracks: Collection[LocalTrack] = None) -> Generator[LocalAlbumCollection, None, None]:
        """Dynamically generate a set of album collections from the tracks in this library"""
        if tracks is None:
            tracks = self.tracks

        tracks = sorted(tracks, key=lambda track: track.album.name if track.album else "")
        grouped = ItemSorter.group_by_field(items=tracks, field="album")
        for name, group in grouped.items():
            if name is None:
                continue

            album = next(
                track.album for track in group
                if track.album and track.album.name.casefold() == name.casefold()
            )

            group = sorted(group, key=lambda track: track.track or 0)
            yield LocalAlbumCollection(**album.model_dump(), tracks=group)

    def artists(self, tracks: Collection[LocalTrack] = None) -> Generator[LocalArtistCollection, None, None]:
        """Dynamically generate a set of artist collections from the tracks in this library"""
        if tracks is None:
            tracks = self.tracks

        tracks = sorted(tracks, key=lambda track: track.artists[0].name if track.artists else "")
        grouped = ItemSorter.group_by_field(items=tracks, field="artists")
        for name, group in grouped.items():
            if name is None:
                continue

            artist = next(
                artist for track in group for artist in track.artists
                if artist.name.casefold() == name.casefold()
            )

            albums = sorted(self.albums(group), key=lambda alb: alb.name)
            for album in albums:
                if not any(artist.name == art.name for art in album.artists):
                    album.artists.append(artist)

            yield LocalArtistCollection(**artist.model_dump(), albums=albums)

    def genres(self, tracks: Collection[LocalTrack] = None) -> Generator[LocalGenreCollection, None, None]:
        """Dynamically generate a set of genre collections from the tracks in this library"""
        if tracks is None:
            tracks = self.tracks

        tracks = sorted(tracks, key=lambda track: track.genre)
        grouped = ItemSorter.group_by_field(items=tracks, field="genres")
        for name, group in grouped.items():
            if name is None:
                continue

            genre = next(
                genre for track in group for genre in track.genres
                if genre.name.casefold() == name.casefold()
            )

            group = sorted(group, key=lambda track: track.track or 0)
            yield LocalGenreCollection(**genre.model_dump(), tracks=group)
