from musify.models.properties.uri import URI
from musify.remote._base import RemoteResource


class RemoteCollection[UT: URI](RemoteResource[UT]):
    pass
