__all__ = []

# we must import all the supported formats here so that they are registered in the registry
from .album import LocalAlbum
from .artist import LocalArtist
from .genre import LocalGenre
