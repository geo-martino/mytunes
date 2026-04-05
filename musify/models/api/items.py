from pydantic import Field

from musify.models.api import BatchReadAllEndpoints, BatchWriteEndpoints, HasEndpoints, Endpoints


class HasLibraryEndpoints[ET: BatchReadAllEndpoints | BatchWriteEndpoints](HasEndpoints):
    library: ET = Field(
        description="Access endpoints for the current user's library items.",
    )


class HasTrackEndpoints[ET: Endpoints | HasLibraryEndpoints](HasEndpoints):
    tracks: ET = Field(
        description="Access track endpoints for the API."
    )


class HasAlbumEndpoints[ET: Endpoints | HasLibraryEndpoints](HasEndpoints):
    albums: ET = Field(
        description="Access album endpoints for the API."
    )


class HasArtistEndpoints[ET: Endpoints | HasLibraryEndpoints](HasEndpoints):
    artists: ET = Field(
        description="Access artist endpoints for the API."
    )


class HasGenreEndpoints[ET: Endpoints | HasLibraryEndpoints](HasEndpoints):
    genres: ET = Field(
        description="Access genre endpoints for the API."
    )
