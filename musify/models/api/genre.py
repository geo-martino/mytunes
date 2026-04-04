from typing import ClassVar, Type

from pydantic import Field

from musify.models.api._endpoints import Endpoints, ItemReadEndpoints, BatchReadEndpoints, \
    BatchReadAllEndpoints, CollectionReadEndpoints, HasEndpoints, BatchWriteEndpoints, HasLibraryEndpoints
from musify.models.collection.genre import RemoteGenreCollection
from musify.models.item.genre import RemoteGenre
from musify.models.properties.uri import URI


class GenreEndpoints[UT: URI, RT: RemoteGenre](Endpoints[UT, RT]):
    type: ClassVar[Type] = RemoteGenre


class GenreReadEndpoints[UT: URI, RT: RemoteGenre](
    GenreEndpoints[UT, RT], ItemReadEndpoints[UT, RT]
):
    pass


class GenreCollectionReadEndpoints[UT: URI, RT: RemoteGenreCollection, IT: RemoteGenre](
    GenreEndpoints[UT, RT], CollectionReadEndpoints[UT, RT, IT]
):
    type: ClassVar[Type] = RemoteGenreCollection


class GenreBatchReadEndpoints[UT: URI, RT: RemoteGenre](
    GenreEndpoints[UT, RT], BatchReadEndpoints[UT, RT]
):
    pass


class GenreBatchReadAllEndpoints[UT: URI, RT: RemoteGenre](
    GenreEndpoints[UT, RT], BatchReadAllEndpoints[UT, RT]
):
    pass


class GenreBatchWriteEndpoints[UT: URI, RT: RemoteGenre](
    GenreEndpoints[UT, RT], BatchWriteEndpoints[UT, RT]
):
    pass


class HasGenreEndpoints[ET: GenreEndpoints | HasLibraryEndpoints](HasEndpoints):
    genres: ET = Field(
        description="Access genre endpoints for the API."
    )
