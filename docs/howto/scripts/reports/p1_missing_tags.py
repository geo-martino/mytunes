from p0 import *

from mytunes.libraries.local.track.field import LocalTrackField
from mytunes.report import report_missing_tags

tags = [
    LocalTrackField.TITLE,
    LocalTrackField.GENRES,
    LocalTrackField.KEY,
    LocalTrackField.BPM,
    LocalTrackField.DATE,
    LocalTrackField.COMPILATION,
    LocalTrackField.IMAGES
]

report_missing_tags(collections=local_library, tags=tags, match_all=False)
