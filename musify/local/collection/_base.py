from musify.local._base import LocalResource
from musify.models._base import CollectionResource


# noinspection PyAbstractClass
class LocalCollection[IT: LocalResource](CollectionResource[IT], LocalResource):
    pass
