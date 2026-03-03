from musify.models.properties.uri import URI, HasURI


class RemoteResource[T: URI](HasURI[T]):
    pass
