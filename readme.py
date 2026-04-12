"""
Fills in the variable fields of the README template and generates README.md file.
"""
from mytunes import PROGRAM_OWNER_USER, PROGRAM_NAME
from mytunes.libraries.local.track import TRACK_FILETYPES
from mytunes.libraries.local.playlist import PLAYLIST_FILETYPES
from mytunes.libraries.local.library import LIBRARY_CLASSES, LocalLibrary
from mytunes.utils import SafeDict
from mytunes.libraries.remote.spotify.wrangle import SpotifyDataWrangler

SRC_FILENAME = "README.template.md"
TRG_FILENAME = SRC_FILENAME.replace(".template", "")


def format_readme():
    """Format the readme template and save the formatted readme"""
    format_map_standard = {
        "program_name": PROGRAM_NAME,
        "program_name_lower": PROGRAM_NAME.lower(),
        "program_owner_user": PROGRAM_OWNER_USER,
    }
    format_map_code = {
        "local_sources": sorted(cls.source for cls in LIBRARY_CLASSES if cls != LocalLibrary),
        "remote_sources": [SpotifyDataWrangler.source],
        "track_filetypes": sorted(TRACK_FILETYPES),
        "playlist_filetypes": sorted(PLAYLIST_FILETYPES),
    }
    format_map_code = {k: "`" + "` `".join(v) + "`" for k, v in format_map_code.items()}
    format_map = SafeDict(format_map_standard | format_map_code)

    with open(SRC_FILENAME, 'r') as file:
        template = file.read()

    formatted = template.format_map(format_map)
    with open(TRG_FILENAME, 'w') as file:
        file.write(formatted)


if __name__ == "__main__":
    format_readme()
    print(f"Formatted {TRG_FILENAME} file using template: {SRC_FILENAME}")
