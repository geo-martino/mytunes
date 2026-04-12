import logging
import sys

from mytunes.logger import STAT

logging.basicConfig(format="%(message)s", level=STAT, stream=sys.stdout)
