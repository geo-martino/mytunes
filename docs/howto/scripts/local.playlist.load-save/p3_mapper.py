from p3 import *

from musify.models.properties.file import PathMapper

playlist = asyncio.run(load_playlist("<PATH TO A PLAYLIST>", path_mapper=PathMapper()))
