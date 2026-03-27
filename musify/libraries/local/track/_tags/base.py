"""
The base processor definition for reading/manipulating tag data in an audio file.
"""
from abc import ABCMeta

import mutagen

from musify.field import TagMap
from musify.libraries.local.track.field import LocalTrackField
from musify.libraries.remote.core.wrangle import RemoteDataWrangler


class TagProcessor[T: mutagen.FileType](metaclass=ABCMeta):
    """
    Base tag processor for reading/writing of tag metadata to a file.

    :param file: The loaded Mutagen object of the file to extract tags from.
    :param tag_map: The map of tag names to tag IDs for the given file type.
    :param remote_wrangler: Optionally, provide a :py:class:`RemoteDataWrangler` object for processing URIs.
        This object will be used to check for and validate a URI tag on the file.
        The tag that is used for reading and writing is set by the ``uri_tag`` class attribute.
        If no ``remote_wrangler`` is given, no URI processing will occur.
    """

    __slots__ = ("file", "tag_map", "remote_wrangler")

    #: The tag field to use as the URI tag in the file's metadata
    uri_tag: LocalTrackField = LocalTrackField.COMMENTS
    #: The separator to use when representing separated tag values as a combined string.
    #: Used when some number type tag values come as a combined string i.e. track number/track total
    num_sep: str = "/"

    @property
    def remote_source(self) -> str | None:
        """The name of the remote service for which this TagProcessor can process remote data."""
        return self.remote_wrangler.source if self.remote_wrangler else None

    @property
    def unavailable_uri_dummy(self) -> str | None:
        """
        The value to use as a URI for an item which does not have an associated remote object.
        An item that has this URI value will be excluded from most remote logic.
        If no remote_wrangler has been assigned to this object, return None.
        """
        return self.remote_wrangler.unavailable_uri_dummy if self.remote_wrangler else None

    def __init__(self, file: T, tag_map: TagMap, remote_wrangler: RemoteDataWrangler | None = None):
        self.file = file
        self.tag_map = tag_map
        self.remote_wrangler = remote_wrangler
