from .._properties.uri import SpotifyResourceURI
from ..._models.api.types import ApiURL, ApiURI, ApiURISequence
from ..._models.properties.uri import HasURI

type SpotifyApiURL[MT: HasURI] = ApiURL[SpotifyResourceURI, MT]
type SpotifyApiURI[MT: HasURI] = ApiURI[SpotifyResourceURI, MT]
type SpotifyApiURISequence[MT: HasURI] = ApiURISequence[SpotifyResourceURI, MT]
