import os
import shutil
from collections.abc import Generator
from pathlib import Path
from typing import Any
from unittest.mock import patch, AsyncMock

import pytest
from faker import Faker
from pytest_mock import MockerFixture

from mytunes.core.properties.path import PathStemMapper, SystemPath
from mytunes.local._collection.library import LocalLibrary
from mytunes.local._collection.library.musicbee import MusicBee
from mytunes.local._collection.library.musicbee import XMLLibraryParser
from mytunes.local._item.track import LocalTrack
from mytunes.local.exception import FileDoesNotExistError
from tests.testers import BaseModelTester, NoUniqueKeyTester

try:
    import xmltodict
except ImportError:
    xmltodict = None


@pytest.mark.skipif(not MusicBee.required_modules_installed, reason="required modules not installed.")
class TestMusicBee(NoUniqueKeyTester):

    @pytest.fixture
    def model(self, musicbee_folder: Path, playlist_folder: Path) -> MusicBee:
        return MusicBee(musicbee_folder=musicbee_folder, playlist_folder=playlist_folder)

    @pytest.fixture
    def tracks(self, tracks: list[LocalTrack]) -> list[LocalTrack]:
        return tracks

    @pytest.fixture
    def settings_xml(self, library_folders: list[Path], tmp_path: Path) -> Generator[dict[str, Any]]:
        """Mocks the XML settings parser to return a sample parsed XML dict."""
        xml = {
            "ApplicationSettings": {
                "Path": str(tmp_path),
                "OrganisationMonitoredFolders": {"string": [str(folder) for folder in library_folders]},
            }
        }

        with patch.object(xmltodict, "parse", return_value=xml):
            yield xml

    @pytest.fixture
    def library_xml(self, tracks: list[LocalTrack], faker: Faker) -> Generator[dict[str, Any]]:
        """Mocks the XML library parser to return a sample parsed XML dict."""
        tracks = tracks[:len(tracks) // 2]  # only map some tracks
        tracks_xml = [MusicBee._track_to_xml(track, track_id=i) for i, track in enumerate(tracks, 1)]
        for track in tracks_xml:
            track["Rating"] = faker.random_int()
            track["Date Added"] = faker.date_time()
            track["Play Date UTC"] = faker.date_time()
            track["Play Count"] = faker.random_int()

        xml = {
            "Major Version": faker.random_int(),
            "Minor Version": faker.random_int(),
            "Application Version": "3.5.8447.35892",
            "Music Folder": str(Path(faker.file_path(depth=faker.random_int(3, 6))).parent),
            "Library Persistent ID": faker.pystr(min_chars=12, max_chars=16),
            "Tracks": {track["Track ID"]: track for track in tracks_xml},
            "Playlists": [],
        }

        with patch.object(XMLLibraryParser, "parse", return_value=xml):
            yield xml

    @pytest.fixture(autouse=True)
    def library_folders(self, tmp_path: Path) -> list[Path]:
        """Temporary library folders for testing."""
        return [
            tmp_path.joinpath(Path("path", "to", "track")),
            tmp_path.joinpath(Path("path", "to", "playlist")),
        ]

    @pytest.fixture(autouse=True)
    def musicbee_folder(self, tmp_path: Path) -> Path:
        """Sets up a temporary MusicBee folder structure with sample data for testing."""
        path = tmp_path.joinpath("MusicBee")
        path.mkdir(parents=True, exist_ok=True)
        return path

    @pytest.fixture(autouse=True)
    def playlist_folder(self, musicbee_folder: Path) -> Path:
        """Creates the Playlists folder inside the temporary MusicBee folder."""
        path = musicbee_folder.joinpath("Playlists")
        path.mkdir(parents=True, exist_ok=True)
        return path

    @pytest.fixture(autouse=True)
    def settings_xml_path(self, musicbee_folder: Path, settings_xml: dict[str, Any]) -> Path:
        """Creates a settings XML file inside the temporary MusicBee folder."""
        path = musicbee_folder.joinpath(MusicBee._xml_settings_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(xmltodict.unparse(settings_xml, short_empty_elements=True, pretty=True))
        return path

    @pytest.fixture(autouse=True)
    def library_xml_path(self, musicbee_folder: Path) -> Path:
        """Creates an empty library XML file inside the temporary MusicBee folder."""
        path = musicbee_folder.joinpath(MusicBee._xml_library_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
        return path

    def test_get_current_system_musicbee_path(
            self, musicbee_folder: Path, platform: str, system_paths: dict[str, str]
    ):
        system_paths |= {platform: musicbee_folder}  # should overwrite the randomly generated one

        model = MusicBee(musicbee_folder=system_paths)
        assert model.musicbee_folder == musicbee_folder
        assert model.path == musicbee_folder.joinpath(MusicBee._xml_library_path)

    def test_get_path_map_from_system_paths(
            self,
            musicbee_folder: Path,
            library_folders: list[Path],
            platform: str,
            system_paths: dict[str, str],
            faker: Faker,
    ):
        system_paths |= {platform: musicbee_folder}  # should overwrite the randomly generated one
        system_paths = SystemPath(**system_paths)

        initial_path_map = {faker.file_path(): faker.file_path()}
        path_mapper = PathStemMapper(stem_map=initial_path_map)

        # WORKAROUND: the musicbee folder is usually in a folder within the music library folder.
        #  We take the parent to account for this
        expected = {str(other.parent): str(musicbee_folder.parent) for other in system_paths.others} | initial_path_map

        model = MusicBee(musicbee_folder=system_paths, path_mapper=path_mapper)
        assert isinstance(model.path_mapper, PathStemMapper)
        assert model.path_mapper.stem_map == expected

    def test_checks_settings_file_exists(self, musicbee_folder: Path, settings_xml_path: Path):
        assert settings_xml_path.is_file()
        MusicBee(musicbee_folder=musicbee_folder)

        os.remove(settings_xml_path)
        with pytest.raises(FileDoesNotExistError):
            MusicBee(musicbee_folder=musicbee_folder)

    def test_checks_library_file_exists(self, musicbee_folder: Path, library_xml_path: Path):
        assert library_xml_path.is_file()
        MusicBee(musicbee_folder=musicbee_folder)

        os.remove(library_xml_path)
        with pytest.raises(FileDoesNotExistError):
            MusicBee(musicbee_folder=musicbee_folder)

    def test_validates_playlist_folder(self, musicbee_folder: Path, playlist_folder: Path):
        assert playlist_folder.is_dir()
        lib = MusicBee(musicbee_folder=musicbee_folder, playlist_folder=playlist_folder.relative_to(musicbee_folder))
        assert lib.playlist_folder == playlist_folder

        shutil.rmtree(playlist_folder)
        lib = MusicBee(musicbee_folder=musicbee_folder)
        assert lib.playlist_folder != playlist_folder  # only set if it exists

    async def test_set_library_folders_from_settings(
            self, model: MusicBee, library_folders: list[Path], settings_xml: dict[str, Any]
    ):
        assert not model.library_folders
        await model.set_library_folders()
        assert model.library_folders == set(library_folders)

    async def test_load_tracks_sets_library_folders(
            self,
            model: MusicBee,
            library_folders: list[Path],
            library_xml: dict[str, Any],
            settings_xml: dict[str, Any],
    ):
        assert not model.library_folders
        await model.load()
        assert model.library_folders == set(library_folders)

    async def test_load_tracks_calls_super(
            self, model: MusicBee, library_folders: list[Path], library_xml: dict[str, Any], mocker: MockerFixture,
    ):
        mock_load = mocker.spy(LocalLibrary, "load_tracks")
        await model.load_tracks()
        mock_load.assert_called_once()

    async def test_load_tracks_enriches_metadata(
            self,
            model: MusicBee,
            tracks: list[LocalTrack],
            library_xml: dict[str, Any],
    ):
        # load is mocked because tracks don't exist on disk, set tracks from super() call load manually
        with patch.object(LocalLibrary, "load_tracks", side_effect=AsyncMock()):
            model.tracks.replace(tracks)
            await model.load_tracks()

        assert len(model.tracks) == len(tracks)
        assert sum(track.play_count is None for track in model.tracks) > 0  # some tracks haven't been enriched

        track_xml_mapped = {track["Location"]: track for track in library_xml["Tracks"].values()}
        for track in tracks:
            if (track_xml := track_xml_mapped.get(str(track.path))) is not None:
                assert track.rating == track_xml["Rating"]
                assert track.added_at == track_xml["Date Added"]
                assert track.last_played_at == track_xml["Play Date UTC"]
                assert track.play_count == track_xml["Play Count"]
            else:
                assert track.rating is None
                assert track.added_at is None
                assert track.last_played_at is None
                assert track.play_count is None

    async def test_save_file_dry_run(self, model: MusicBee, tracks: list[LocalTrack], library_xml: dict[str, Any]):
        model.tracks.replace(tracks)

        with patch.object(XMLLibraryParser, "unparse", return_value="text") as mock_unparse:
            await model.save(dry_run=True)
            mock_unparse.assert_not_called()

    async def test_save_file_saves_xml(self, model: MusicBee, tracks: list[LocalTrack], library_xml: dict[str, Any]):
        model.tracks.replace(tracks)

        with patch.object(XMLLibraryParser, "unparse", return_value="text") as mock_unparse:
            result = await model.save(dry_run=False)
            mock_unparse.assert_called_once_with(result)

            with model.xml_library_path.open("r") as xml_file:
                assert xml_file.read() == mock_unparse.return_value

    async def test_save_file_maps_tracks(
            self, model: MusicBee, tracks: list[LocalTrack], library_xml: dict[str, Any]
    ):
        model.tracks.replace(tracks)
        assert len(library_xml["Tracks"]) < len(model.tracks)

        result = await model.save(dry_run=True)
        assert len(result["Tracks"]) == len(model.tracks)


@pytest.mark.skipif(not XMLLibraryParser.required_modules_installed, reason="required modules not installed.")
class TestXMLLibraryParser(BaseModelTester):

    @pytest.fixture
    def model(self, xml: str) -> XMLLibraryParser:
        return XMLLibraryParser(source=xml)

    @pytest.fixture
    def xml(self) -> str:
        """Returns a sample MusicBee XML library as a string."""
        # noinspection PyPep8,HttpUrlsUsage
        return """
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple Computer//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
	<key>Major Version</key><integer>3</integer>
	<key>Minor Version</key><integer>5</integer>
	<key>Application Version</key><string>3.5.8447.35892</string>
	<key>Music Folder</key><string>file://localhost/path/to/music</string>
	<key>Library Persistent ID</key><string>3D76B2A6FD362901</string>
	<key>Tracks</key>
	<dict>
		<key>1</key>
		<dict>
			<key>Track ID</key><integer>1</integer>
			<key>Persistent ID</key><string>E8C4D399F0878EA7</string>
			<key>Name</key><string>title 2</string>
			<key>Artist</key><string>artist 2; another artist</string>
			<key>Album</key><string>album artist 2</string>
			<key>Album Artist</key><string>various</string>
			<key>Track Number</key><integer>3</integer>
			<key>Track Count</key><integer>4</integer>
			<key>Genre1</key><string>Pop Rock</string>
			<key>Genre2</key><string>Musical</string>
			<key>Year</key><integer>2024</integer>
			<key>BPM</key><integer>200.56</integer>
			<key>Disc Number</key><integer>2</integer>
			<key>Disc Count</key><integer>3</integer>
			<key>Compilation</key><false/>
			<key>Comments</key><string>spotify:track:1TjVbzJUAuOvas1bL00TiH</string>
			<key>Total Time</key><integer>30000</integer>
			<key>Rating</key><integer>20</integer>
			<key>Size</key><integer>410910</integer>
			<key>Kind</key><string>MP3</string>
			<key>Bit Rate</key><integer>96</integer>
			<key>Sample Rate</key><integer>44100</integer>
			<key>Date Modified</key><date>2023-12-07T15:46:22Z</date>
			<key>Date Added</key><date>2023-05-20T23:22:11Z</date>
			<key>Play Date UTC</key><date>2023-07-20T06:12:26Z</date>
			<key>Play Count</key><integer>5</integer>
			<key>Track Type</key><string>File</string>
			<key>Location</key><string>file://localhost/track/noiSE_mP3.mp3</string>
		</dict>
		<key>2</key>
		<dict>
			<key>Track ID</key><integer>2</integer>
			<key>Persistent ID</key><string>FF019498DA3C4984</string>
			<key>Name</key><string>title 1</string>
			<key>Artist</key><string>artist 1</string>
			<key>Album</key><string>album artist 1</string>
			<key>Album Artist</key><string>various</string>
			<key>Track Number</key><integer>1</integer>
			<key>Track Count</key><integer>4</integer>
			<key>Genre1</key><string>Pop</string>
			<key>Genre2</key><string>Rock</string>
			<key>Genre3</key><string>Jazz</string>
			<key>Year</key><integer>2020</integer>
			<key>BPM</key><integer>120.12</integer>
			<key>Disc Number</key><integer>1</integer>
			<key>Disc Count</key><integer>3</integer>
			<key>Compilation</key><true/>
			<key>Comments</key><string>spotify:track:6fWoFduMpBem73DMLCOh1Z</string>
			<key>Total Time</key><integer>20000</integer>
			<key>Rating</key><integer>50</integer>
			<key>Size</key><integer>1818191</integer>
			<key>Kind</key><string>FLAC</string>
			<key>Bit Rate</key><integer>706</integer>
			<key>Sample Rate</key><integer>44100</integer>
			<key>Date Modified</key><date>2023-05-22T17:03:17Z</date>
			<key>Date Added</key><date>2023-05-23T21:33:20Z</date>
			<key>Play Date UTC</key><date>2023-09-02T08:21:22Z</date>
			<key>Play Count</key><integer>10</integer>
			<key>Track Type</key><string>File</string>
			<key>Location</key><string>file://localhost/track/NOISE_FLaC.flac</string>
		</dict>
		<key>3</key>
		<dict>
			<key>Track ID</key><integer>3</integer>
			<key>Persistent ID</key><string>397EF3EAF91D2354</string>
			<key>Name</key><string>excluded title 1</string>
			<key>Artist</key><string>excluded artist 1</string>
			<key>Album</key><string>excluded album artist 1</string>
			<key>Album Artist</key><string>various</string>
			<key>Track Number</key><integer>1</integer>
			<key>Track Count</key><integer>4</integer>
			<key>Genre1</key><string>Pop</string>
			<key>Genre2</key><string>Rock</string>
			<key>Genre3</key><string>Jazz</string>
			<key>Year</key><integer>2020</integer>
			<key>BPM</key><integer>120.12</integer>
			<key>Disc Number</key><integer>1</integer>
			<key>Disc Count</key><integer>3</integer>
			<key>Compilation</key><true/>
			<key>Comments</key><string>spotify:track:6fWoFduMpBem73DMLCOhab</string>
			<key>Total Time</key><integer>20000</integer>
			<key>Rating</key><integer>70</integer>
			<key>Size</key><integer>1818191</integer>
			<key>Kind</key><string>FLAC</string>
			<key>Bit Rate</key><integer>706</integer>
			<key>Sample Rate</key><integer>44100</integer>
			<key>Date Modified</key><date>2023-05-20T20:43:35Z</date>
			<key>Date Added</key><date>2023-07-04T11:12:00Z</date>
			<key>Play Date UTC</key><date>2023-09-15T22:10:04Z</date>
			<key>Play Count</key><integer>12</integer>
			<key>Track Type</key><string>File</string>
			<key>Location</key><string>file://localhost/playlist/exclude_me.flac</string>
		</dict>
		<key>4</key>
		<dict>
			<key>Track ID</key><integer>4</integer>
			<key>Persistent ID</key><string>02B76D443BDEB4A2</string>
			<key>Name</key><string>title 3</string>
			<key>Artist</key><string>artist 3</string>
			<key>Album</key><string>album artist 3</string>
			<key>Album Artist</key><string>various</string>
			<key>Track Number</key><integer>2</integer>
			<key>Track Count</key><integer>4</integer>
			<key>Genre1</key><string>Dance</string>
			<key>Genre2</key><string>Techno</string>
			<key>Year</key><integer>2021</integer>
			<key>BPM</key><integer>120.0</integer>
			<key>Disc Number</key><integer>1</integer>
			<key>Disc Count</key><integer>2</integer>
			<key>Compilation</key><true/>
			<key>Comments</key><string>spotify:track:4npv0xZO9fVLBmDS2XP9Bw</string>
			<key>Total Time</key><integer>20023</integer>
			<key>Rating</key><integer>80</integer>
			<key>Size</key><integer>302199</integer>
			<key>Kind</key><string>M4A</string>
			<key>Bit Rate</key><integer>98</integer>
			<key>Sample Rate</key><integer>44100</integer>
			<key>Date Modified</key><date>2023-05-20T20:43:36Z</date>
			<key>Date Added</key><date>2023-10-17T14:42:37Z</date>
			<key>Play Date UTC</key><date>2023-11-01T15:11:11Z</date>
			<key>Play Count</key><integer>20</integer>
			<key>Track Type</key><string>File</string>
			<key>Location</key><string>file://localhost/track/noise_m4a.m4a</string>
		</dict>
		<key>5</key>
		<dict>
			<key>Track ID</key><integer>5</integer>
			<key>Persistent ID</key><string>623B817C9962115E</string>
			<key>Name</key><string>excluded title 2</string>
			<key>Artist</key><string>excluded artist 2</string>
			<key>Album</key><string>excluded album artist 2</string>
			<key>Album Artist</key><string>various</string>
			<key>Track Number</key><integer>3</integer>
			<key>Track Count</key><integer>4</integer>
			<key>Genre1</key><string>Pop Rock</string>
			<key>Genre2</key><string>Musical</string>
			<key>Year</key><integer>2024</integer>
			<key>BPM</key><integer>200.56</integer>
			<key>Disc Number</key><integer>2</integer>
			<key>Disc Count</key><integer>3</integer>
			<key>Compilation</key><true/>
			<key>Comments</key><string>spotify:track:1TjVbzJUAuOvas1bL00Tab</string>
			<key>Total Time</key><integer>30000</integer>
			<key>Rating</key><integer>100</integer>
			<key>Size</key><integer>410910</integer>
			<key>Kind</key><string>MP3</string>
			<key>Bit Rate</key><integer>96</integer>
			<key>Sample Rate</key><integer>44100</integer>
			<key>Date Modified</key><date>2023-05-20T20:43:35Z</date>
			<key>Date Added</key><date>2023-08-29T17:16:15Z</date>
			<key>Play Date UTC</key><date>2023-11-09T11:22:33Z</date>
			<key>Play Count</key><integer>18</integer>
			<key>Track Type</key><string>File</string>
			<key>Location</key><string>file://localhost/playlist/exclude_me_2.mp3</string>
		</dict>
		<key>6</key>
		<dict>
			<key>Track ID</key><integer>6</integer>
			<key>Persistent ID</key><string>333F48944377444C</string>
			<key>Name</key><string>title 4</string>
			<key>Artist</key><string>artist 4</string>
			<key>Album</key><string>album artist 4</string>
			<key>Album Artist</key><string>various</string>
			<key>Track Number</key><integer>4</integer>
			<key>Track Count</key><integer>4</integer>
			<key>Genre1</key><string>Metal</string>
			<key>Genre2</key><string>Rock</string>
			<key>Year</key><integer>2023</integer>
			<key>BPM</key><integer>200.56</integer>
			<key>Disc Number</key><integer>3</integer>
			<key>Disc Count</key><integer>4</integer>
			<key>Compilation</key><false/>
			<key>Comments</key><string>spotify:track:unavailable</string>
			<key>Total Time</key><integer>32001</integer>
			<key>Rating</key><integer>40</integer>
			<key>Size</key><integer>1193637</integer>
			<key>Kind</key><string>WMA</string>
			<key>Bit Rate</key><integer>96</integer>
			<key>Sample Rate</key><integer>44100</integer>
			<key>Date Modified</key><date>2023-05-20T20:43:36Z</date>
			<key>Date Added</key><date>2023-05-29T15:26:22Z</date>
			<key>Play Date UTC</key><date>2023-05-30T22:57:24Z</date>
			<key>Play Count</key><integer>200</integer>
			<key>Track Type</key><string>File</string>
			<key>Location</key><string>file://localhost/track/noise_wma.wma</string>
		</dict>
	</dict>
	<key>Playlists</key>
	<array>
		<dict>
			<key>Playlist ID</key><integer>6550</integer>
			<key>Playlist Persistent ID</key><string>CFBEF1CA18E03</string>
			<key>All Items</key><true/>
			<key>Name</key><string>Recently Added</string>
			<key>Playlist Items</key>
			<array>
				<dict>
					<key>Track ID</key><integer>4</integer>
				</dict>
				<dict>
					<key>Track ID</key><integer>5</integer>
				</dict>
				<dict>
					<key>Track ID</key><integer>3</integer>
				</dict>
				<dict>
					<key>Track ID</key><integer>6</integer>
				</dict>
				<dict>
					<key>Track ID</key><integer>2</integer>
				</dict>
				<dict>
					<key>Track ID</key><integer>1</integer>
				</dict>
			</array>
		</dict>
		<dict>
			<key>Playlist ID</key><integer>6566</integer>
			<key>Playlist Persistent ID</key><string>C356C2E4B12CC417</string>
			<key>All Items</key><true/>
			<key>Name</key><string>Simple Playlist</string>
			<key>Playlist Items</key>
			<array>
				<dict>
					<key>Track ID</key><integer>2</integer>
				</dict>
				<dict>
					<key>Track ID</key><integer>1</integer>
				</dict>
				<dict>
					<key>Track ID</key><integer>6</integer>
				</dict>
			</array>
		</dict>
		<dict>
			<key>Playlist ID</key><integer>6567</integer>
			<key>Playlist Persistent ID</key><string>4A99495C0BC1926D</string>
			<key>All Items</key><true/>
			<key>Name</key><string>Complex Match</string>
			<key>Description</key><string>This has got some complex matching</string>
			<key>Playlist Items</key>
			<array/>
		</dict>
		<dict>
			<key>Playlist ID</key><integer>6570</integer>
			<key>Playlist Persistent ID</key><string>B526A789D1FC5173</string>
			<key>All Items</key><true/>
			<key>Name</key><string>The Best Playlist Ever</string>
			<key>Description</key><string>I am a description</string>
			<key>Playlist Items</key>
			<array>
				<dict>
					<key>Track ID</key><integer>2</integer>
				</dict>
				<dict>
					<key>Track ID</key><integer>6</integer>
				</dict>
			</array>
		</dict>
	</array>
</dict>
</plist>
        """.strip()

    @pytest.fixture
    def path(self, xml: str, tmp_path: Path) -> Path:
        """Writes the sample MusicBee XML library to a temporary file and returns the Path to this file."""
        path = tmp_path.joinpath("library.xml")
        path.write_text(xml, encoding="utf-8")
        return path

    async def test_parse_unparse_basic(self, xml: str, path: Path):
        parser = XMLLibraryParser(source=path, path_keys=MusicBee._xml_library_path_keys)

        parsed = await parser.parse()
        assert parsed["Major Version"] == 3
        assert parsed["Minor Version"] == 5
        assert parsed["Application Version"] == "3.5.8447.35892"
        assert parsed["Music Folder"] == "path/to/music"
        assert parsed["Library Persistent ID"] == "3D76B2A6FD362901"
        assert len(parsed["Tracks"]) == 6
        assert len(parsed["Playlists"]) == 4

        assert await parser.unparse(parsed) == xml.rstrip('\n') + '\n'

    async def test_parse_unparse_with_changes(self, path: Path):
        parser = XMLLibraryParser(source=path, path_keys=MusicBee._xml_library_path_keys)

        parsed = await parser.parse()
        parsed["Major Version"] = 7
        parsed["Minor Version"] = 9
        parsed["Music Folder"] = str(Path("this", "is", "a", "new", "path"))

        xml = await parser.unparse(parsed)
        path.write_text(xml, encoding="utf-8")

        result = await parser.parse()
        assert result["Major Version"] == 7
        assert result["Minor Version"] == 9
        assert result["Application Version"] == "3.5.8447.35892"
        assert result["Music Folder"] == str(Path("this", "is", "a", "new", "path"))
        assert result["Library Persistent ID"] == "3D76B2A6FD362901"
        assert len(result["Tracks"]) == 6
        assert len(result["Playlists"]) == 4
