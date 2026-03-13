from typing import ClassVar, Type

from pydantic import Field

from musify.models.api._endpoints import Endpoints, ReadItemEndpoints, ReadItemsEndpoints, \
    ReadSavedEndpoints, ReadCollectionEndpoints, HasEndpoints, WriteSavedEndpoints
from musify.models.collection.genre import RemoteGenreCollection
from musify.models.item.genre import RemoteGenre
from musify.models.properties.uri import URI


class GenreEndpoints[UT: URI, RT: RemoteGenre](Endpoints[UT, RT]):
    type: ClassVar[Type] = RemoteGenre


class GenreReadItemEndpoints[UT: URI, RT: RemoteGenre](
    GenreEndpoints[UT, RT], ReadItemEndpoints[UT, RT]
):
    pass


class GenreReadItemsEndpoints[UT: URI, RT: RemoteGenre](
    GenreEndpoints[UT, RT], ReadItemsEndpoints[UT, RT]
):
    pass


class GenreReadCollectionEndpoints[UT: URI, RT: RemoteGenreCollection](
    GenreEndpoints[UT, RT], ReadCollectionEndpoints[UT, RT]
):
    type: ClassVar[Type] = RemoteGenreCollection


class GenreReadSavedEndpoints[UT: URI, RT: RemoteGenre](
    GenreEndpoints[UT, RT], ReadSavedEndpoints[UT, RT]
):
    pass


class GenreWriteSavedEndpoints[UT: URI, RT: RemoteGenre](
    GenreEndpoints[UT, RT], WriteSavedEndpoints[UT, RT]
):
    pass


class HasGenreEndpoints[ET: GenreEndpoints](HasEndpoints):
    genres: ET = Field(
        description="Access genre endpoints for the API."
    )
