from collections.abc import Iterable
from typing import ClassVar, Any

from pydantic.json_schema import JsonSchemaValue

from musify.spotify import SpotifyModel, SpotifyResource
from .._properties.uri import SpotifyURIBase
from ..._models.api import Endpoints, BatchWriteEndpoints


class SpotifyEndpoints[UT: SpotifyURIBase, RT: SpotifyResource](
    Endpoints[UT, RT], SpotifyModel
):
    # TODO: drop this on aiorequestful v2
    _id_path: ClassVar[str] = "id"
    _url_path: ClassVar[str] = "href"


class _SpotifyLibraryEndpoints[UT: SpotifyURIBase, RT: SpotifyResource](
    BatchWriteEndpoints[UT, RT], SpotifyEndpoints[UT, RT],
):
    @staticmethod
    def _generate_add_batch_kwargs(values: Iterable[Any]) -> JsonSchemaValue:
        return {"params": {"uris": ",".join(map(str, values))}}

    @staticmethod
    def _generate_remove_batch_kwargs(values: Iterable[Any]) -> JsonSchemaValue:
        return {"params": {"uris": ",".join(map(str, values))}}
