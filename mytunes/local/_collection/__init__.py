__all__ = []

# must import all the supported formats here so that they are registered in the registry
from .album import LocalAlbumCollection
from .artist import LocalArtistCollection
from .folder import Folder
from .genre import LocalGenreCollection
from .library import *
from .playlist import *
