from p2 import *

from datetime import date

from mytunes.libraries.remote.core.object import RemoteAlbum


def match_date(alb: RemoteAlbum, start: date, end: date) -> bool:
    """Match ``start`` and ``end`` dates to the release date of the given ``alb``"""
    if alb.date:
        return start <= alb.date <= end
    if alb.month:
        return start.year <= alb.year <= end.year and start.month <= alb.month <= end.month
    if alb.year:
        return start.year <= alb.year <= end.year
    return False
