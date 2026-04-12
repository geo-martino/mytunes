from p3 import *

from mytunes.file.path_mapper import PathMapper

playlist = asyncio.run(load_playlist("<PATH TO A PLAYLIST>", path_mapper=PathMapper()))
