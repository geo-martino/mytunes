from musify._models.api.types import ApiURL, ApiURI, ApiURISequence
from musify._models.properties.uri import HasURI
from .._properties.uri import SpotifyResourceURI

type SpotifyApiURL[MT: HasURI] = ApiURL[SpotifyResourceURI, MT]
type SpotifyApiURI[MT: HasURI] = ApiURI[SpotifyResourceURI, MT]
type SpotifyApiURISequence[MT: HasURI] = ApiURISequence[SpotifyResourceURI, MT]
