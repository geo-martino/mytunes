from aiorequestful.auth import Authoriser

from musify.models.properties.uri import URI
from musify.remote import RemoteModel
from musify.remote.api._base import RemoteEndpoints
from musify.remote.user import RemoteUser


class UserEndpoints[AT: Authoriser, UT: URI, RT: RemoteUser](RemoteEndpoints[AT, UT, RT]):
    pass


class UserGetSingleEndpoints[AT: Authoriser, UT: URI, RT: RemoteUser](
    UserEndpoints[AT, UT, RT], RemoteEndpoints[AT, UT, RT]
):
    pass


class HasUserEndpoints[ET: UserEndpoints](RemoteModel):
    users: ET
