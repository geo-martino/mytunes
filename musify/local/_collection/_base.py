from musify.local._base import LocalModel
from ..._models.collection import CollectionModel


# noinspection PyAbstractClass
class LocalCollection[IT: LocalModel](CollectionModel[IT], LocalModel):
    pass
