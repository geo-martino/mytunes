from p2 import *

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

library.restore_tracks(backup, tags=tags)
