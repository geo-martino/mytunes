from ._base import AudioStore, GeneralAudioStore

__all__ = ["AudioStore", "GeneralAudioStore"]

# we must import all the supported formats here so that they are registered in the registry
from .bandcamp import BandcampStore
from .juno_download import JunoDownloadStore
from .qobuz import QobuzStore
from .seven_digital import SevenDigitalStore
