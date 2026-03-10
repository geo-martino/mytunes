from musify.remote.api.types import ApiURL, ApiURI, ApiURISequence
from musify.spotify import SpotifyResource
from musify.spotify.properties.uri import SpotifyResourceURI

type SpotifyApiURL[MT: SpotifyResource] = ApiURL[SpotifyResourceURI, MT]
type SpotifyApiURI[MT: SpotifyResource] = ApiURI[SpotifyResourceURI, MT]
type SpotifyApiURISequence[MT: SpotifyResource] = ApiURISequence[SpotifyResourceURI, MT]
