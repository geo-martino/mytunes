import asyncio
import itertools
from asyncio import Semaphore
from collections.abc import Generator, Iterable, Collection
from functools import cached_property
from pathlib import Path
from typing import Annotated, ClassVar, final, Self

from mutagen import MutagenError
from mutagen.mp3 import HeaderNotFoundError
from pydantic import Field, field_validator, BeforeValidator, DirectoryPath, TypeAdapter, PrivateAttr, PositiveInt
from termcolor import colored

from musify._types import to_set
from musify.exception import MusifyError, MusifyValueError
from musify.local.collection._base import LocalCollection
from musify.local.collection.album import LocalAlbumCollection
from musify.local.collection.artist import LocalArtistCollection
from musify.local.collection.folder import Folder
from musify.local.collection.genre import LocalGenreCollection
from musify.local.collection.playlist import LocalPlaylist
from musify.local.item.track import LocalTrack, HasLocalTracks, TagContext
from musify.logger import STAT
from musify.models.collection.library import MutableLibrary
from musify.models.properties.file import PathMapper
from musify.models.properties.uri import URI
from musify.models.result import TotalCountResult, LenLogFormatter, Result
from musify.processors_new.filters import Filter, ValuesFilter
from musify.processors_new.sort import ItemSorter
from musify.utils import afilter


class LibraryURIsResult[T: LocalTrack](TotalCountResult):
    """Stores the results of the URIs on loaded tracks in a local library."""
    source: str = Field(
        description="The remote library source these URIs are associated with.",
    )
    available: Annotated[
        tuple[T, ...],
        LenLogFormatter(
            width=6, alignment="right", colour="red", colour_attributes=["bold"], condition=lambda x: x == 0
        ),
        LenLogFormatter(
            width=6, alignment="right", colour="green", colour_attributes=["bold"], condition=lambda x: x > 0
        ),
    ] = Field(
        description="The tracks which are available on this source i.e. the track has a matching URI set.",
        default_factory=tuple
    )
    missing: Annotated[
        tuple[T, ...],
        LenLogFormatter(
            width=6, alignment="right", colour="blue", colour_attributes=["bold"], condition=lambda x: x == 0
        ),
        LenLogFormatter(
            width=6, alignment="right", colour="green", colour_attributes=["bold"], condition=lambda x: x > 0
        ),
    ] = Field(
        description=(
            "The tracks which are missing matching URIs "
            "i.e. it is unknown whether the track exists on this source or not."
        ),
        default_factory=tuple
    )
    unavailable: Annotated[
        tuple[T, ...],
        LenLogFormatter(
            width=6, alignment="right", colour="green", colour_attributes=["bold"], condition=lambda x: x == 0
        ),
        LenLogFormatter(
            width=6, alignment="right", colour="red", colour_attributes=["bold"], condition=lambda x: x > 0
        ),
    ] = Field(
        description=(
            "The tracks which are confirmed to be unavailable on this source "
            "i.e. the track does not have a matching URI set because it doesn't exist on the remote library."
        ),
        default_factory=tuple
    )

    @classmethod
    def from_tracks(cls, source: str, tracks: Iterable[T]) -> Self:
        """Create a result from the given tracks."""
        return cls(
            source=source,
            available=filter(lambda x: cls._is_available(source, x), tracks),
            missing=filter(lambda x: cls._is_missing(source, x), tracks),
            unavailable=filter(lambda x: cls._is_unavailable(source, x), tracks),
        )

    @staticmethod
    def _is_available(source: str, track: T) -> bool:
        return any(uri.source == source and uri.exists for uri in track.uris)

    @staticmethod
    def _is_missing(source: str, track: T) -> bool:
        return all(uri.source != source for uri in track.uris)

    @staticmethod
    def _is_unavailable(source: str, track: T) -> bool:
        return any(uri.source == source and not uri.exists for uri in track.uris)


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

    library_folders: Annotated[set[DirectoryPath], BeforeValidator(to_set)] = Field(
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
    def _convert_playlist_names_to_filter[T: str | Iterable[str]](names: T) -> T | ValuesFilter[str]:
        if not names or isinstance(names, Filter):
            return names

        names = to_set(names)
        return ValuesFilter(values=names)

    async def load(self) -> None:
        self.logger.info(f"Loading tracks and playlists in {self.source} library", header=1)

        await self.load_tracks()
        await self.load_playlists()

        header = f"{self.source.upper()} TRACK AND PLAYLIST URIS"
        results = {"TRACKS": self._generate_track_uris_results()}
        results |= self._generate_playlist_uris_results()
        table = LibraryURIsResult.generate_table(results=results, header=header)

        self.logger.print_line(STAT)
        self.logger.stat(table)

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

            return self._track_adapter.validate_python(file, context=self.tracks_load_settings)

        except (MusifyError, MutagenError, ValueError, OSError, RuntimeError) as ex:  # TODO: drop RuntimeError?
            self.logger.debug(f"Load error for track: {path} - {ex}")
            self.errors.append(path)

    @cached_property
    def _track_adapter(self) -> TypeAdapter[LocalTrack]:
        return TypeAdapter[LocalTrack](LocalTrack.annotation)

    async def load_tracks(self) -> bool:
        if not (paths := set(self._track_paths)):
            return False

        self.logger.info(f"Loading {len(paths)} tracks in {self.source} library", header=2)

        bar = self.logger.get_asynchronous_iterator(
            map(self.load_track, paths),
            desc="Loading tracks",
            unit="tracks",
            initial=0,
            total=len(paths)
        )
        self.tracks.replace(filter(None, await bar))

        self._log_errors("Could not load the following tracks")
        return True

    @property
    def _track_paths(self) -> Generator[Path, None, None]:
        if not self.library_folders:
            return

        extensions: set[str] = LocalTrack.supported_extensions

        folders = self.library_folders
        folder_message = "folder" if len(folders) == 1 else "folders"
        message = f"Scanning {len(folders)} {self.source} library {folder_message} for tracks with extensions:"
        self.logger.info(message, header=2, hidden=", ".join(sorted(extensions)))

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
        return LibraryURIsResult.from_tracks(self.source, self.tracks)

    ###########################################################################
    ## Playlists
    ###########################################################################
    async def load_playlist(self, path: str | Path) -> LocalPlaylist | None:
        """
        Loads the playlist at the given ``path`` and assigns optional arguments using this library's attributes.

        Handles exceptions by logging paths which produce errors to internal list of ``errors``.
        """
        try:
            async with self.concurrency:
                self.logger.debug(f"Loading playlist: {path}")

                playlist = self._playlist_adapter.validate_python(path)
                playlist.path_mapper = self.path_mapper
                return await playlist.load(self.tracks)

        except (MusifyError, ValueError, FileNotFoundError) as ex:
            self.logger.debug(f"Load error for playlist: {path} - {ex}")
            self.errors.append(path)

    @cached_property
    def _playlist_adapter(self) -> TypeAdapter[LocalPlaylist]:
        return TypeAdapter[LocalPlaylist](LocalPlaylist.annotation)

    async def load_playlists(self) -> bool:
        if not (paths := set(self._playlist_paths)):
            return False

        self.logger.info(f"Loading {len(paths)} playlists in {self.source} library", header=2)

        bar = self.logger.get_asynchronous_iterator(
            map(self.load_playlist, paths),
            desc="Loading playlists",
            unit="playlists",
            initial=0,
            total=len(paths)
        )
        playlists = {pl.name: pl for pl in sorted(filter(None, await bar), key=lambda x: x.name.casefold())}
        self.playlists.replace(playlists, extract_keys=False)

        self._log_errors("Could not load the following playlists")
        return True

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

        # noinspection PyTypeChecker
        extensions: set[str] = LocalPlaylist.supported_extensions

        folder_message = "folder" if len(folders) == 1 else "folders"
        message = f"Scanning {len(folders)} {self.source} library {folder_message} for playlists with extensions:"
        self.logger.info(message, header=2, hidden=", ".join(sorted(extensions)))

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

    def log_playlists(self) -> None:
        results = self._generate_playlist_uris_results()
        header = f"{self.source.upper()} PLAYLIST URIS"
        table = LibraryURIsResult.generate_table(results=results, header=header)

        self.logger.stat(table)

    def _generate_playlist_uris_results(self) -> dict[str, LibraryURIsResult[LocalTrack]]:
        return {
            name: LibraryURIsResult.from_tracks(self.source, playlist.tracks)
            for name, playlist in self.playlists.items()
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

        self.logger.info(f"Saving {len(self.playlists)} playlists in {self.source} {self.type}", header=2)

        bar = self.logger.get_asynchronous_iterator(
            map(_save_playlist, self.playlists.values()),
            desc="Updating playlists",
            unit="playlists",
            initial=0,
            total=len(self.playlists)
        )
        return dict(await bar)

    def _log_save_tracks_header(self) -> None:
        message = f"Saving {len(self.playlists)} playlists in {self.source} {self.type}"

        match self:
            case HasName() as named:
                message += f": {named.name!r}"
            case Library() as library if isinstance(library.source, str):
                message += f": {library.source!r}"

        self.logger.info(message, header=2)

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
            tracks = sorted(tracks, key=lambda track: track.filename)
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

            album = next(track.album for track in group if track.album and track.album.name.casefold() == name)
            tracks = sorted(tracks, key=lambda track: track.track or 0)
            yield LocalAlbumCollection(**album.model_dump(), tracks=tracks)

    def artists(self, tracks: Collection[LocalTrack] = None) -> Generator[LocalArtistCollection, None, None]:
        """Dynamically generate a set of artist collections from the tracks in this library"""
        if tracks is None:
            tracks = self.tracks

        tracks = sorted(tracks, key=lambda track: track.artists[0].name if track.artists else "")
        grouped = ItemSorter.group_by_field(items=tracks, field="artists")
        for name, group in grouped.items():
            if name is None:
                continue

            artist = next(artist for track in group for artist in track.artists if artist.name.casefold() == name)
            albums = sorted(self.albums(group), key=lambda album: album.name)
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

            genre = next(genre for track in group for genre in track.genres if genre.name.casefold() == name)
            tracks = sorted(tracks, key=lambda track: track.track or 0)
            yield LocalGenreCollection(**genre.model_dump(), tracks=tracks)
