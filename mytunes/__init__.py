"""Welcome to MyTunes"""
import warnings
from pathlib import Path

PROGRAM_NAME = "MyTunes"
PROGRAM_OWNER_NAME = "George Martin Marino"
PROGRAM_OWNER_USER = "geo-martino"
PROGRAM_OWNER_EMAIL = f"gm.engineer+{PROGRAM_NAME.lower()}@pm.me"
PROGRAM_URL = f"https://github.com/{PROGRAM_OWNER_USER}/{PROGRAM_NAME.lower()}"

MODULE_ROOT: str = Path(__file__).parent.name
PACKAGE_ROOT: Path = Path(__file__).parent.parent

__all__ = [
    "PROGRAM_NAME",
    "PROGRAM_OWNER_NAME",
    "PROGRAM_OWNER_USER",
    "PROGRAM_OWNER_EMAIL",
    "PROGRAM_URL",
    "MODULE_ROOT",
    "PACKAGE_ROOT",
]

# WORKAROUND: get way too many warnings when trying to dump tracks, this stops them
warnings.filterwarnings(
    "ignore", module="pydantic", category=UserWarning, message=".*PydanticSerializationUnexpectedValue.*"
)

# we must import all the supported URI formats here so that they are registered in the registry
from .spotify.uri import SpotifyResourceURI, SpotifyUserURI
