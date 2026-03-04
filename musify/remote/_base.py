from musify.models import AttributeModel
from musify.models.properties.uri import URI, HasURI


class RemoteModel(AttributeModel):
    pass


class RemoteResource[UT: URI](RemoteModel, HasURI[UT]):
    def __hash__(self):
        return hash(self.uri)
