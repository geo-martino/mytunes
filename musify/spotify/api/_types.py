from musify.models.api.types import ApiURL, ApiURI, ApiURISequence
from musify.models.properties.uri import HasURI
from musify.spotify.properties.uri import SpotifyResourceURI

type SpotifyApiURL[MT: HasURI] = ApiURL[SpotifyResourceURI, MT]
type SpotifyApiURI[MT: HasURI] = ApiURI[SpotifyResourceURI, MT]
type SpotifyApiURISequence[MT: HasURI] = ApiURISequence[SpotifyResourceURI, MT]
