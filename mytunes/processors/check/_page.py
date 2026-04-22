from collections.abc import Sequence

from pydantic import Field, field_validator

from mytunes.core.api import RemoteAPI, HasAPI, Endpoints
from mytunes.core.collection import CollectionModel
from mytunes.core.properties.asynch import HasAsyncOperations
from mytunes.core.properties.uri import HasURI
from mytunes.core.user import RemoteUser
from mytunes.exception import MyTunesValidationError
from .._base.inputs import PageProcessor
from mytunes.core.api.user import HasUserEndpoints


# noinspection PyAbstractClass
class CollectionsPage[API: RemoteAPI, CT: HasURI](PageProcessor, HasAPI[API], HasAsyncOperations):
    collections: Sequence[CollectionModel] = Field(
        description="The collections to be checked on this page."
    )

    @field_validator("api", mode="after")
    @classmethod
    def _validate_api_has_necessary_endpoints(cls, api: API) -> API:
        if not isinstance(api, RemoteAPI):
            raise MyTunesValidationError(f"API must be an instance of RemoteAPI, got {type(api).__name__!r}")

        return api

    @property
    def source(self) -> str:
        """The log name of the remote service that this searcher is running on."""
        return self.api.source

    @property
    def user(self) -> RemoteUser | None:
        """The user to create playlists for."""
        return self.api.user if isinstance(self.api, Endpoints | HasUserEndpoints) else None

    @property
    def total(self) -> int:
        """The number of collections to be checked."""
        return len(self.collections)
