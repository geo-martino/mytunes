import pytest

from mytunes._base.resource import ResourceModel
from mytunes.core.genre import RemoteGenre
from mytunes.core.album import RemoteAlbum
from mytunes.core.artist import RemoteArtist
from mytunes.core.genre import Genre
from mytunes.core.playlist import RemotePlaylist, Playlist
from mytunes.core.album import Album
from mytunes.core.artist import Artist
from mytunes.core.track import RemoteTrack, Track
from mytunes.local.genre import LocalGenre
from mytunes.local.artist import LocalArtist
from mytunes.local.album import LocalAlbum
from mytunes.local.playlist import LocalPlaylist
from mytunes.local.track import LocalTrack


@pytest.mark.parametrize(
    "source,target",
    [
        (LocalTrack, RemoteTrack),
        (LocalPlaylist, RemotePlaylist),
        (LocalAlbum, RemoteAlbum),
        (LocalArtist, RemoteArtist),
        (LocalGenre, RemoteGenre),
    ]
)
def test_base_models_have_common_unique_attributes(source: ResourceModel, target: ResourceModel):
    """Needed to ensure all supported `merge_...` operations work correctly."""
    assert source.__unique_attributes__ & target.__unique_attributes__


@pytest.mark.parametrize("model_type", [Track, Playlist, Album, Artist, Genre])
def test_final_models_have_common_unique_attributes(model_type: type[ResourceModel]):
    """Needed to ensure comparison across libraries work correctly."""
    assert all(kls.__unique_attributes__ for kls in model_type.registered_submodels)

    common_unique_attributes = {attr for kls in model_type.registered_submodels for attr in kls.__unique_attributes__}
    for kls in model_type.registered_submodels:
        common_unique_attributes &= kls.__unique_attributes__

    assert common_unique_attributes
