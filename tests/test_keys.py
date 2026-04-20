import pytest

from mytunes._base.resource import ResourceModel
from mytunes.core._collection.playlist import RemotePlaylist, Playlist
from mytunes.core._item.track import RemoteTrack, Track
from mytunes.local._collection.playlist import LocalPlaylist
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
def test_common_unique_attributes(source: ResourceModel, target: ResourceModel):
    """Needed to ensure all supported `merge_...` operations work correctly."""
    assert source.__unique_attributes__ & target.__unique_attributes__


# TODO: this shouldn't pass if the above test fails
#  passes because not all final classes are registered when test is called
#  either restructure to fix or import final classes manually
@pytest.mark.parametrize("model_type", [Track, Playlist])
def test_registry_has_unique_attributes(model_type: type[ResourceModel]):
    """Needed to ensure comparison across libraries work correctly."""
    assert all(kls.__unique_attributes__ for kls in model_type.registered_submodels)

    common_unique_attributes = {attr for kls in model_type.registered_submodels for attr in kls.__unique_attributes__}
    print(common_unique_attributes)
    for kls in model_type.registered_submodels:
        common_unique_attributes &= kls.__unique_attributes__
        print(common_unique_attributes, kls.__unique_attributes__)

    assert common_unique_attributes
