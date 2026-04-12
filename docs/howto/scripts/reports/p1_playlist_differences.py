from p0 import *

from mytunes.report import report_playlist_differences

report_playlist_differences(source=local_library, reference=remote_library)
