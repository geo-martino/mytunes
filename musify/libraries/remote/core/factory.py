"""
Configuration relating to the :py:mod:`Remote` module.

This configuration can be used to inject dependencies into dependencies throughout the module.
"""
import inspect
from dataclasses import dataclass
from functools import partial

from musify.libraries.remote.core.api import RemoteAPI
from musify.libraries.remote.core.base import RemoteObject
from musify.libraries.remote.core.object import RemoteTrack, RemoteAlbum, RemotePlaylist, RemoteArtist
from musify.libraries.remote.core.types import RemoteObjectType


@dataclass
class RemoteObjectFactory[A: RemoteAPI, PL: RemotePlaylist, TR: RemoteTrack, AL: RemoteAlbum, AR: RemoteArtist]:
    """Stores the key object classes for a remote source"""
    #: The playlist type for this remote source
    playlist: type[PL]
    #: The track type for this remote source
    track: type[TR]
    #: The album type for this remote source
    album: type[AL]
    #: The artist type for this remote source
    artist: type[AR]
    #: An optional :py:class:`RemoteAPI` object to pass to each object on instantiation
    api: A = None

    def __getitem__(self, __key: RemoteObjectType) -> type[RemoteObject]:
        return self.__getattribute__(__key.name.lower())

    def __getattribute__(self, __name: str):
        attribute = object.__getattribute__(self, __name)
        if inspect.isclass(attribute) and issubclass(attribute, RemoteObject) and self.api is not None:
            executable = partial(attribute, api=self.api)

            # need to assign the class methods back to the partial object to ensure near seamless user use
            for key in dir(attribute):
                value = getattr(attribute, key)
                if inspect.ismethod(value) and not key.startswith("_"):
                    setattr(executable, key, partial(value, api=self.api))
            return executable
        return attribute
