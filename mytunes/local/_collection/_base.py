from mytunes.core.collection import CollectionModel
from mytunes.local._base import LocalModel


# noinspection PyAbstractClass
class LocalCollection[IT: LocalModel](CollectionModel[IT], LocalModel):
    pass
