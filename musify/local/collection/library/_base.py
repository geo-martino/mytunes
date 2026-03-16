import itertools
import textwrap
from collections.abc import Generator, Iterable, Mapping, Sequence
from pathlib import Path
from typing import Annotated, ClassVar, Any, final

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
from musify.local.collection.playlist import LocalPlaylist
from musify.local.item.track import LocalTrack, TagDumpContext
from musify.logger import STAT
from musify.models.collection.library import MutableLibrary, RestoreType
from musify.models.properties.file import PathMapper
from musify.models.properties.logger import HasLogger
from musify.models.properties.uri import URI
from musify.processors_new import Result
from musify.processors_new.filters import Filter, ValuesFilter
from musify.processors_new.sort import ItemSorter


@final
class LocalLibrary(
    MutableLibrary[URI, LocalTrack, URI | Path, LocalPlaylist], LocalCollection[LocalTrack]
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
    errors: list[str] = Field(
        description="List of errors encountered while loading the library.",
        default_factory=list,
    )

    @field_validator("playlist_filter", mode="before", check_fields=True)
    @staticmethod
    def _convert_playlist_names_to_filter[T: str | Iterable[str]](names: T) -> T | ValuesFilter[str]:
        if not names or isinstance(names, Filter):
            return names

        names = to_set(names)
        return ValuesFilter(values=names)

    def _iter_track_paths(self) -> Generator[Path, None, None]:
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

    async def load(self) -> None:
        self.logger.info(f"Loading tracks and playlists in {self.source} library", header=1)

        await self.load_tracks()
        await self.load_playlists()

        self.logger.print_line(STAT)
        rows = [self.log_tracks(skip_log=True)] + self.log_playlists(skip_log=True)
        log = tabulate(
            rows,
            tablefmt="orgtbl",
            colalign=("left", "right", "right", "right", "right"),
        )
        self.logger.stat(log)

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
            track = TypeAdapter[LocalTrack](LocalTrack.annotation).validate_python(file)
            return track
        except (MusifyError, ValueError, OSError, RuntimeError) as ex:  # TODO: drop RuntimeError?
            self.logger.debug(f"Load error for track: {path} - {ex}")
            self.errors.append(path)

    async def load_tracks(self) -> bool:
        if not (paths := set(self._iter_track_paths())):
            return False

        self.logger.info(f"Loading {len(paths)} tracks in {self.source} library", header=2)

        # WARNING: making this run asynchronously will break tqdm; bar will get stuck after 1-2 ticks
        bar = self.logger.get_asynchronous_iterator(
            map(self.load_track, paths),
            desc="Loading tracks",
            unit="tracks",
            initial=0,
            total=len(paths)
        )
        self.tracks[:] = filter(lambda tr: tr is not None, await bar)

        self._log_errors("Could not load the following tracks")
        return True

    def log_tracks(self, skip_log: bool = False) -> tuple[str, ...]:
        header = textwrap.shorten(f"{self.source.upper()} URIS", 20, placeholder="...")
        row = (
            colored(header, "cyan", attrs=["bold"]),
            colored(f"{sum(track.has_uri is True for track in self.tracks)} available", "green"),
            colored(f"{sum(track.has_uri is None for track in self.tracks)} missing", "red"),
            colored(f"{sum(track.has_uri is False for track in self.tracks)} unavailable", "yellow"),
            colored(f"{len(self.tracks)} total", "blue", attrs=["bold"]),
        )

        if not skip_log:
            log = tabulate(
                [row],
                tablefmt="orgtbl",
                colalign=("left", "right", "right", "right", "right"),
            )
            self.logger.stat(log)

        return row

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
        For each track in this Library, save its tags to file.

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
            if not dry_run:
                await track.save(file)

            return track.path, tags

        self.logger.info(f"Saving {len(self.tracks)} tracks in {self.source} library", header=2)

        # WARNING: making this run asynchronously will break tqdm; bar will get stuck after 1-2 ticks
        bar = self.logger.get_asynchronous_iterator(
            map(_save_track, self.tracks),
            desc="Updating tracks",
            unit="tracks",
            initial=0,
            total=len(self.tracks)
        )
        return dict(await bar)

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
            playlist = TypeAdapter[LocalPlaylist](LocalPlaylist.annotation).validate_python(path)
            playlist.path_mapper = self.path_mapper
            return await playlist.load(self.tracks)
        except (MusifyError, ValueError, FileNotFoundError) as ex:
            self.logger.debug(f"Load error for playlist: {path} - {ex}")
            self.errors.append(path)

    async def load_playlists(self) -> bool:
        if not (paths := set(self._iter_playlist_paths())):
            return False

        self.logger.info(f"Loading {len(paths)} playlists in {self.source} library", header=2)

        # WARNING: making this run asynchronously will break tqdm; bar will get stuck after 1-2 ticks
        bar = self.logger.get_asynchronous_iterator(
            map(self.load_playlist, paths),
            desc="Loading playlists",
            unit="playlists",
            initial=0,
            total=len(paths)
        )
        playlists = filter(lambda pl: pl is not None, await bar)
        playlists = {pl.name: pl for pl in sorted(playlists, key=lambda x: x.name.casefold())}
        self.playlists.replace(playlists, extract_keys=False)

        self._log_errors("Could not load the following playlists")
        return True

    def log_playlists(self, skip_log: bool = False) -> list[tuple[str, ...]]:
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
            return rows

        if not skip_log:
            header = colored(f"{self.source.upper()} PLAYLISTS", "cyan", attrs=["bold"])
            log = header + ":\n" + tabulate(
                rows,
                tablefmt="orgtbl",
                colalign=("left", "right", "right", "right", "right"),
            )

            self.logger.stat(log)

        return rows

    async def save_playlists(self, dry_run: bool = True) -> dict[str, Result]:
        """
        For each Playlist in this Library, saves its associate tracks and its settings (if applicable) to file.

        :param dry_run: Run function, but do not modify the file on the disk.
        :return: A map of the playlist name to the results of its sync as a :py:class:`Result` object.
        """
        async def _save_playlist(pl: LocalPlaylist) -> tuple[str, Result]:
            return pl.name, await pl.save(dry_run=dry_run)

        self.logger.info(f"Saving {len(self.playlists)} playlists in {self.source} library", header=2)

        # WARNING: making this run asynchronously will break tqdm; bar will get stuck after 1-2 ticks
        bar = self.logger.get_asynchronous_iterator(
            map(_save_playlist, self.playlists.values()),
            desc="Updating playlists",
            unit="playlists",
            initial=0,
            total=len(self.playlists)
        )
        return dict(await bar)

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
    ## Restore
    ###########################################################################
    @validate_call
    def restore_tracks(
            self, backup: RestoreType[str | Path], tags: Annotated[set[str], BeforeValidator(to_set)] = ()
    ) -> int:
        """
        Restore track tags from a backup to loaded track objects. This does not save the updated tags.

        Backup may be in the form of either:
            * An iterable of dictionaries where dictionary is ``{<Dump of track data>}``
            * A mapping of ``{<path>: {<Dump of track data>}}``
            * A mapping of ``{"tracks": {<path>: {<Dump of track data>}}}``

        :param backup: Backup data. See description for accepted formats.
        :param tags: Set of tags to restore.
        :return: The number of tracks restored.
        """
        tags = (tags or set(LocalTrack.__tag_attributes__)) | set(LocalTrack.__tag_attributes__)
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
    def _extract_tracks_from_backup(backup: RestoreType[str | Path]) -> dict[Path, Mapping[str, Any]]:
        if isinstance(backup, Mapping) and "tracks" in backup:
            backup = backup["tracks"]

        if isinstance(backup, Mapping):
            backup = {Path(path): track_map for path, track_map in backup.items()}
        else:
            backup = {Path(track_map["path"]): track_map for track_map in backup}
        return backup
