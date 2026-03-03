from musify.models import AttributeModel
from musify.models.properties.uri import URI, HasURI


class RemoteModel(AttributeModel):
    pass


class RemoteResource[T: URI](RemoteModel, HasURI[T]):
    pass
