from collections.abc import Iterable
from typing import ClassVar, Any

from pydantic.json_schema import JsonSchemaValue

from musify.models.api import Endpoints
from musify.spotify import SpotifyModel, SpotifyResource
from musify.spotify.properties.uri import _SpotifyURIBase


class SpotifyEndpoints[UT: _SpotifyURIBase, RT: SpotifyResource](
    Endpoints[UT, RT], SpotifyModel
):
    # TODO: drop this on aiorequestful v2
    _id_path: ClassVar[str] = "id"
    _url_path: ClassVar[str] = "href"

    # just define this here for write saved endpoints, it's the same for every endpoint type
    @staticmethod
    def _generate_add_batch_kwargs(values: Iterable[Any]) -> JsonSchemaValue:
        return {"params": {"uris": ",".join(map(str, values))}}

    @staticmethod
    def _generate_remove_batch_kwargs(values: Iterable[Any]) -> JsonSchemaValue:
        return {"params": {"uris": ",".join(map(str, values))}}
