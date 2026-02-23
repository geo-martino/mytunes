import asyncio
import json
import logging

from musify.local.collection.library.musicbee import MusicBee
from musify.models.properties.file import PathStemMapper

path_mapper = PathStemMapper(
    stem_map={"../": r"M:\Music", "M:/Music": "/Volumes/Media/Music", r"M:\Music": "/Volumes/Media/Music"}
)

library = MusicBee(musicbee_folder="/Volumes/Media/Music/MusicBee", path_mapper=path_mapper)
handler = logging.StreamHandler()
formatter = logging.Formatter('%(message)s')
handler.setFormatter(formatter)
library.logger.addHandler(handler)
library.logger.setLevel(logging.DEBUG)

# paths = list(library._iter_track_paths())
asyncio.run(library.load())

with open("library.json", "w") as f:
    json.dump(library.generate_backup(), f, indent=2)

exit(0)

asyncio.run(library.set_library_folders())
# paths = list(library._iter_track_paths())
# paths = [
#     next(path for path in paths if path.suffix.lstrip(".") == "flac"),
#     next(path for path in paths if path.suffix.lstrip(".") == "mp3"),
#     next(path for path in paths if path.suffix.lstrip(".") == "wma"),
#     next(path for path in paths if path.suffix.lstrip(".") == "m4a"),
# ]
paths = [
    "/Volumes/Media/Music/The North Borders/06 - Jets.flac",
]
for path in paths:
    track = asyncio.run(library.load_track(path))
    print(json.dumps(track.model_dump(mode="json"), indent=2))
