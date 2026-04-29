from pydantic import Field

from mytunes.core.api import ItemReadAllEndpoints, BatchWriteEndpoints, HasEndpoints, Endpoints


class HasLibraryEndpoints[ET: ItemReadAllEndpoints | BatchWriteEndpoints](HasEndpoints[ET]):
    library: ET = Field(
        description="Access endpoints for the current user's library items.",
    )


class HasTrackEndpoints[ET: Endpoints | HasLibraryEndpoints](HasEndpoints[ET]):
    tracks: ET = Field(
        description="Access track endpoints for the API."
    )


class HasAlbumEndpoints[ET: Endpoints | HasLibraryEndpoints](HasEndpoints[ET]):
    albums: ET = Field(
        description="Access album endpoints for the API."
    )


class HasArtistEndpoints[ET: Endpoints | HasLibraryEndpoints](HasEndpoints[ET]):
    artists: ET = Field(
        description="Access artist endpoints for the API."
    )


class HasGenreEndpoints[ET: Endpoints | HasLibraryEndpoints](HasEndpoints[ET]):
    genres: ET = Field(
        description="Access genre endpoints for the API."
    )
