from mytunes.properties.uri import HasURI
from .._properties.uri import SpotifyResourceURI
from ...core.api.types import ApiURL, ApiURI, ApiURISequence

type SpotifyApiURL[MT: HasURI] = ApiURL[SpotifyResourceURI, MT]
type SpotifyApiURI[MT: HasURI] = ApiURI[SpotifyResourceURI, MT]
type SpotifyApiURISequence[MT: HasURI] = ApiURISequence[SpotifyResourceURI, MT]
