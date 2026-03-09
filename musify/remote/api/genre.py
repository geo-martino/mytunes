from typing import ClassVar, Type

from pydantic import Field

from musify.models.properties.uri import URI
from musify.remote.api._endpoints import RemoteEndpoints, RemoteGetSingleEndpoints, RemoteGetManyEndpoints, \
    RemoteGetSavedEndpoints, RemoteCollectionEndpoints, HasEndpoints
from musify.remote.collection.genre import RemoteGenreCollection
from musify.remote.item.genre import RemoteGenre


class GenreEndpoints[UT: URI, RT: RemoteGenre](RemoteEndpoints[UT, RT]):
    type: ClassVar[Type] = RemoteGenre


class GenreGetSingleEndpoints[UT: URI, RT: RemoteGenre](
    GenreEndpoints[UT, RT], RemoteGetSingleEndpoints[UT, RT]
):
    pass


class GenreGetManyEndpoints[UT: URI, RT: RemoteGenre](
    GenreEndpoints[UT, RT], RemoteGetManyEndpoints[UT, RT]
):
    pass


class GenreCollectionEndpoints[UT: URI, RT: RemoteGenreCollection](
    GenreEndpoints[UT, RT], RemoteCollectionEndpoints[UT, RT]
):
    type: ClassVar[Type] = RemoteGenreCollection


class GenreGetSavedEndpoints[UT: URI, RT: RemoteGenre](
    GenreEndpoints[UT, RT], RemoteGetSavedEndpoints[UT, RT]
):
    pass


class HasGenreEndpoints[ET: GenreEndpoints](HasEndpoints):
    genres: ET = Field(
        description="Access genre endpoints for the API."
    )
