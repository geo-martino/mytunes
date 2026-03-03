## DEPRECATED

from musify.types import MusifyEnum


def test_unique_list():
    test = [5, 5, 1, 2, 6, 2, 2, 3, 7, 3, 3, 2, 3, 7, 8, 3, 2, 6, 1, 2, 7, 8, 1, 5]
    result = MusifyEnum._unique_list(test)
    assert len(result) == len(set(test))
    assert result == [5, 1, 2, 6, 3, 7, 8]
