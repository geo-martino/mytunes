import sys
from collections.abc import Mapping
from contextlib import suppress
from pathlib import PureWindowsPath, PurePosixPath, Path, PurePath
from typing import Self, Any

from mytunes.exception import MyTunesError
from mytunes.local.exception import FileDoesNotExistError
from pydantic import model_validator, BaseModel, Field, ValidationError


class LocalSystemPaths(BaseModel):
    windows: PureWindowsPath | None = Field(
        description="The directory to use for Windows systems.",
        validation_alias="win",
        default=None,
    )
    mac: PurePosixPath | None = Field(
        description="The directory to use for Mac systems.",
        default=None,
    )
    linux: PurePosixPath | None = Field(
        description="The directory to use for Linux systems.",
        validation_alias="lin",
        default=None,
    )

    @property
    def path(self) -> Path | None:
        """The path for the current system."""
        match sys.platform:
            case "win32":
                return Path(self.windows) if self.windows is not None else None
            case "darwin":
                return Path(self.mac) if self.mac is not None else None
            case "linux":
                return Path(self.linux) if self.linux is not None else None
            case platform:
                raise MyTunesError(f"Unrecognised current platform: {platform!r}.")

    @property
    def others(self) -> list[PurePath]:
        """The paths for other systems."""
        # noinspection PyTypeChecker
        return [path for path in self.model_dump().values() if path is not None and path != self.path]

    def __str__(self):
        return str(self.path)

    @classmethod
    def get_current_system_path[T](cls, data: T | Mapping[str, Any]) -> T | Path:
        """Validate and extract the current system path from the given data."""
        if not isinstance(data, Mapping):
            return data

        with suppress(ValidationError):
            return cls.model_validate(data).path
        return data
