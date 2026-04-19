import pytest
from mytunes._models import ResourceModel
from mytunes._models.collection.playlist import RemotePlaylist
from mytunes._models.item.album import RemoteAlbum
from mytunes._models.item.artist import RemoteArtist
from mytunes._models.item.track import RemoteTrack
from mytunes.local._collection.playlist import LocalPlaylist
from mytunes.local._item import LocalAlbum, LocalArtist
from mytunes.local._item.track import LocalTrack


@pytest.mark.parametrize(
    "source,target",
    [
        (LocalTrack, RemoteTrack),
        (LocalPlaylist, RemotePlaylist),
        # known to not be supported for this
        # (LocalAlbum, RemoteAlbum),
        # (LocalArtist, RemoteArtist),
    ]
)
def test_overlapping_unique_keys_in_types(source: ResourceModel, target: ResourceModel):
    """Needed to ensure all supported `merge_...` operations work correctly."""
    assert source.__unique_attributes__ & target.__unique_attributes__
