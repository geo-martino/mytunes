from p2 import *

# ...or select which tags you wish to save like so
from mytunes.libraries.local.track.field import LocalTrackField

tags = [
    LocalTrackField.TITLE,
    LocalTrackField.GENRES,
    LocalTrackField.KEY,
    LocalTrackField.BPM,
    LocalTrackField.DATE,
    LocalTrackField.COMPILATION,
    LocalTrackField.IMAGES
]

results = asyncio.run(track.save(tags=tags, replace=True, dry_run=False))

# print a list of the tags that were saved
print([tag.name for tag in results.updated])
