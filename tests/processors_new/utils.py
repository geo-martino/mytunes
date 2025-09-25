import string
from pathlib import Path
from random import randrange, choice


def create_random_file(path: Path, size: int | None = None) -> None:
    """Generates a random file of a given ``size`` in bytes in the test cache folder."""
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w") as file:
        for _ in range(0, size or randrange(int(6*10e3), int(10e6))):
            file.write(choice(string.ascii_letters))
