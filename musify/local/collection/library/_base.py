import itertools
import itertools
import textwrap
from collections.abc import Generator, Iterable, Mapping
from pathlib import Path
from typing import Annotated, ClassVar, Any

from pydantic import Field, field_validator, BeforeValidator, DirectoryPath, TypeAdapter, validate_call
from tabulate import tabulate
from termcolor import colored

from musify._types import to_set
from musify.exception import MusifyError, MusifyValueError
from musify.local.collection._base import LocalCollection
from musify.local.collection.album import LocalAlbumCollection
from musify.local.collection.artist import LocalArtistCollection
from musify.local.collection.folder import Folder
from musify.local.collection.genre import LocalGenreCollection
from musify.local.collection.playlist import LocalPlaylist, LocalPlaylistType
from musify.local.item.track import LocalTrack, LocalTrackType
from musify.logger import STAT, HEADER_PREFIX
from musify.models.collection.library import MutableLibrary
from musify.models.properties.file import PathMapper
from musify.processors_new import Result
from musify.processors_new.filters import Filter, ValuesFilter
from musify.processors_new.sort import ItemSorter
from musify.utils import get_discriminator_values

type RestoreTracksType = Iterable[Mapping[str, Any]] | Mapping[str | Path, Mapping[str, Any]]


class LocalLibrary(
    LocalCollection, MutableLibrary[str, LocalTrack, str, LocalPlaylist]
):
    """
    Represents a local library, providing various methods for manipulating
    tracks and playlists across an entire local library collection.
    """

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
    playlist_filter: ValuesFilter[str] | None = Field(
        description="The filter to apply when loading playlists. Filters playlist by name.",
        default=None
    )
    path_mapper: PathMapper = Field(
        description="Mapper to use when mapping paths stored in the playlist files.",
        default_factory=PathMapper,
    )
    errors: list[str] = Field(
        description="List of errors encountered while loading the library.",
        default_factory=list,
    )

    @field_validator("playlist_filter", mode="before", check_fields=True)
    @staticmethod
    def _convert_playlist_names_to_filter[T](names: T | str | Iterable[str]) -> T | ValuesFilter[str]:
        if not names or isinstance(names, Filter):
            return names

        names = to_set(names)
        return ValuesFilter(values=names)

    def _iter_track_paths(self) -> Generator[Path, None, None]:
        if not self.library_folders:
            return

        extensions = get_discriminator_values(LocalTrackType)
        for folder in self.library_folders:
            for path in folder.rglob(f"[!.]*"):
                if path.suffix.lstrip(".").casefold() not in extensions:
                    continue
                if any(part in path.parts for part in self._ignore_folders):
                    continue

                yield path

    def _iter_playlist_paths(self) -> Generator[Path, None, None]:
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

        extensions = get_discriminator_values(LocalPlaylistType)

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

    async def load(self) -> None:
        self.logger.debug(f"Load {self.source} library: START")
        self.logger.info(
            f"\33[1;95m ->\33[1;97m Loading tracks and playlists in {self.source} library \33[0m"
        )

        await self.load_tracks()
        await self.load_playlists()

        self.logger.print_line(STAT)
        self.log_tracks()
        self.log_playlists()

        self.logger.print_line()
        self.logger.debug(f"Load {self.source} library: DONE\n")

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
            self.logger.debug(f"Loading track: {path}")
            file = await LocalTrack.load_file(path)
            track: LocalTrack = TypeAdapter(LocalTrackType).validate_python(file)
            return track
        except (MusifyError, ValueError, OSError, RuntimeError) as ex:  # TODO: drop RuntimeError?
            self.logger.debug(f"Load error for track: {path} - {ex}")
            self.errors.append(path)

    async def load_tracks(self) -> None:
        self.logger.debug(f"Find {self.source} track paths: START")
        paths = set(self._iter_track_paths())
        self.logger.debug(f"Find {self.source} track paths: DONE")
        if not paths:
            return

        self.logger.debug(f"Load {self.source} tracks: START")
        self.logger.info(
            HEADER_PREFIX +
            colored(f"Loading {len(paths)} tracks in {self.source} library", "cyan", attrs=["bold"])
        )

        # WARNING: making this run asynchronously will break tqdm; bar will get stuck after 1-2 ticks
        bar = self.logger.get_synchronous_iterator(
            paths, desc="Loading tracks", unit="tracks", total=len(paths)
        )
        self.tracks[:] = filter(lambda tr: tr is not None, [await self.load_track(path) for path in bar])

        self._log_errors("Could not load the following tracks")
        self.logger.debug(f"Load {self.source} tracks: DONE\n")

    def log_tracks(self) -> str:
        row = (
            colored(textwrap.shorten("LIBRARY URIS", 20, placeholder="..."), "cyan", attrs=["bold"]),
            colored(f"{sum(track.has_uri is True for track in self.tracks)} available", "green"),
            colored(f"{sum(track.has_uri is None for track in self.tracks)} missing", "red"),
            colored(f"{sum(track.has_uri is False for track in self.tracks)} unavailable", "yellow"),
            colored(f"{len(self.tracks)} total", "blue", attrs=["bold"]),
        )
        log = tabulate(
            [row],
            tablefmt="orgtbl",
            colalign=("left", "right", "right", "right", "right"),
        )

        self.logger.stat(log)
        return log

    ###########################################################################
    ## Playlists
    ###########################################################################
    async def load_playlist(self, path: str | Path) -> LocalPlaylist | None:
        """
        Loads the playlist at the given ``path`` and assigns optional arguments using this library's attributes.

        Handles exceptions by logging paths which produce errors to internal list of ``errors``.
        """
        try:
            self.logger.debug(f"Loading playlist: {path}")
            playlist: LocalPlaylist = TypeAdapter(LocalPlaylistType).validate_python(path)
            playlist.path_mapper = self.path_mapper
            return await playlist.load(self.tracks)
        except (MusifyError, ValueError, FileNotFoundError) as ex:
            self.logger.debug(f"Load error for playlist: {path} - {ex}")
            self.errors.append(path)

    async def load_playlists(self) -> None:
        self.logger.debug(f"Find {self.source} playlist paths: START")
        paths = set(self._iter_playlist_paths())
        self.logger.debug(f"Find {self.source} playlist paths: DONE")
        if not paths:
            return

        self.logger.debug(f"Load {self.source} playlists: START")
        self.logger.info(
            HEADER_PREFIX +
            colored(f"Loading {len(paths)} playlists in {self.source} library", "cyan", attrs=["bold"])
        )

        # WARNING: making this run asynchronously will break tqdm; bar will get stuck after 1-2 ticks
        bar = self.logger.get_synchronous_iterator(
            paths, desc="Loading playlists", unit="playlists", total=len(paths)
        )
        playlists = filter(lambda pl: pl is not None, [await self.load_playlist(path) for path in bar])

        self.playlists.clear()
        self.playlists.update({pl.name: pl for pl in sorted(playlists, key=lambda x: x.name.casefold())}, extract_keys=False)

        self._log_errors("Could not load the following playlists")
        self.logger.debug(f"Load {self.source} playlists: DONE\n")

    def log_playlists(self) -> str:
        rows = []
        for name, playlist in self.playlists.items():
            row = (
                colored(textwrap.shorten(name, 20, placeholder="..."), "white"),
                colored(f"{sum(track.has_uri is True for track in playlist.tracks)} available", "green"),
                colored(f"{sum(track.has_uri is None for track in playlist.tracks)} missing", "red"),
                colored(f"{sum(track.has_uri is False for track in playlist.tracks)} unavailable", "yellow"),
                colored(f"{len(playlist.tracks)} total", "blue", attrs=["bold"]),
            )
            rows.append(row)

        if not rows:
            return ""

        header = colored(f"{self.source.upper()} PLAYLISTS", "cyan", attrs=["bold"]) + ":\n"
        log = header + tabulate(
            rows,
            tablefmt="orgtbl",
            colalign=("left", "right", "right", "right", "right"),
        )

        self.logger.stat(log)
        return log

    async def save_playlists(self, dry_run: bool = True) -> dict[str, Result]:
        """
        For each Playlist in this Library, saves its associate tracks and its settings (if applicable) to file.

        :param dry_run: Run function, but do not modify the file on the disk.
        :return: A map of the playlist name to the results of its sync as a :py:class:`Result` object.
        """
        async def _save_playlist(pl: LocalPlaylist) -> tuple[str, Result]:
            return pl.name, await pl.save(dry_run=dry_run)

        # WARNING: making this run asynchronously will break tqdm; bar will get stuck after 1-2 ticks
        results = await self.logger.get_asynchronous_iterator(
            map(_save_playlist, self.playlists.values()),
            desc="Updating playlists",
            unit="tracks",
            total=len(self.playlists)
        )
        return dict(results)

    ###########################################################################
    ## Collections
    ###########################################################################
    def folders(self) -> Generator[Folder, None, None]:
        """
        Dynamically generate a set of folder collections from the tracks in this library.
        Folder collections are generated relevant to the library folder it is found in.
        """
        def get_relative_path(track: LocalTrack) -> Path:
            """Return path of a track relative to the library folders of this library"""
            for folder in self.library_folders:
                if track.path.is_relative_to(folder):
                    return track.path.relative_to(folder).parent

            raise MusifyValueError(f"Track path is not relative to any library folders: {track.path}")

        groups = itertools.groupby(sorted(self.tracks, key=get_relative_path), get_relative_path)
        for path, group in groups:
            yield Folder(tracks=group, name=path.name)

    def albums(self) -> Generator[LocalAlbumCollection, None, None]:
        """Dynamically generate a set of album collections from the tracks in this library"""
        tracks = sorted(self.tracks, key=lambda track: track.album.name if track.album else "")
        grouped = ItemSorter.group_by_field(items=tracks, field="album")
        for album, group in grouped.items():
            if album is None:
                continue
            yield LocalAlbumCollection(tracks=group, name=album)

    def artists(self) -> Generator[LocalArtistCollection, None, None]:
        """Dynamically generate a set of artist collections from the tracks in this library"""
        tracks = sorted(self.tracks, key=lambda track: track.artists[0].name if track.artists else "")
        grouped = ItemSorter.group_by_field(items=tracks, field="artists")
        for artist, group in grouped.items():
            if artist is None:
                continue
            yield LocalArtistCollection(tracks=group, name=artist)

    def genres(self) -> Generator[LocalGenreCollection, None, None]:
        """Dynamically generate a set of genre collections from the tracks in this library"""
        tracks = sorted(self.tracks, key=lambda track: track.genre)
        grouped = ItemSorter.group_by_field(items=tracks, field="genres")
        for genre, group in grouped.items():
            if genre is None:
                continue
            yield LocalGenreCollection(tracks=group, name=genre)

    ###########################################################################
    ## Backup/restore
    ###########################################################################
    def generate_backup(self) -> dict:
        """Generate a backup dictionary of this library's state."""
        dump = self.model_dump(
            mode="json", exclude_none=True
        )
        return dump

    @validate_call
    def restore_tracks(
            self, backup: RestoreTracksType, tags: Annotated[set[str], BeforeValidator(to_set)] = ()
    ) -> int:
        """
        Restore track tags from a backup to loaded track objects. This does not save the updated tags.

        :param backup: Backup data in the form ``{<path>: {<Map of JSON formatted track data>}}``
        :param tags: Set of tags to restore.
        :return: The number of tracks restored.
        """
        tags = (tags or LocalTrack.__tag_fields__) | LocalTrack.__tag_fields__
        backup = self._extract_tracks_from_backup(backup)

        count = 0
        for track in self.tracks:
            if not (track_backup := backup.get(track.path)):
                continue

            for tag in tags:
                if tag in track_backup:
                    setattr(track, tag, track_backup[tag])
            count += 1

        return count

    @staticmethod
    def _extract_tracks_from_backup(backup: RestoreTracksType) -> dict[Path, Mapping[str, Any]]:
        if isinstance(backup, Mapping):
            backup = {Path(path): track_map for path, track_map in backup.items()}
        else:
            backup = {Path(track_map["path"]): track_map for track_map in backup}
        return backup
