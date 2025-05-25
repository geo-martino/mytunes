from io import BytesIO
from pathlib import Path
from random import choice, sample

import mutagen.id3
import pytest
from PIL import Image
from aioresponses import aioresponses, CallbackResult
from faker import Faker

from musify.model import MusifyResource
from musify.model.properties.image import ImageURL, ImageFile
from tests.utils import SimpleURI


@pytest.fixture(scope="session")
def faker() -> Faker:
    """Sets up and yields a basic Faker object for fake data"""
    return Faker()


@pytest.fixture(scope="session")
def mock_response():
    with aioresponses() as m:
        yield m


# TODO: this needs to be moved somewhere else, the models fixture is not available at this level
# add layer to the testers hierarchy to allow this fixture to be used in the model tests
@pytest.fixture
def uri(models: list[MusifyResource], faker: Faker) -> SimpleURI:
    return SimpleURI.from_id(
        faker.random_int(int(10e9), int(10e10)), kind=choice(models).type, source=faker.word()
    )


@pytest.fixture
def uris(models: list[MusifyResource], faker: Faker) -> list[SimpleURI]:
    seen = set()
    uris = []

    for model in models:
        source = None
        while source is None or source in seen:
            source = faker.word()

        uris.append(SimpleURI.from_id(faker.random_int(int(10e9), int(10e10)), kind=model.type, source=source))
        seen.add(source)

    return uris


@pytest.fixture
def images(faker: Faker) -> list[bytes]:
    return [
        faker.image(
            size=(faker.random_int(100, 300), faker.random_int(100, 300)),
            image_format=choice(["jpeg", "png"])
        )
        for _ in range(faker.random_int(3, 5))
    ]


@pytest.fixture
def image_types(images: list[bytes]) -> set[str]:
    """Fixture to provide a valid image type."""
    types = {
        name for name, enum in vars(mutagen.id3.PictureType).items()
        if isinstance(enum, mutagen.id3.PictureType)
    }
    return set(sample(list(types), len(images)))


@pytest.fixture
def image_files(image_types: set[str], faker: Faker, tmp_path: Path) -> list[Path]:
    """Fixture to provide a list of image files."""
    image_files = []

    for _ in range(faker.random_int(3, 5)):
        size = (faker.random_int(100, 300), faker.random_int(100, 300))
        image_bytes = faker.image(size=size, image_format=choice(["jpeg", "png"]))

        path = tmp_path.joinpath(faker.file_name(category="image"))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(image_bytes)
        img = Image.open(BytesIO(image_bytes))

        image_file = ImageFile(
            path=path,
            type=choice(list(image_types)),
            mime=img.get_format_mimetype(),
            height=img.height,
            width=img.width
        )
        image_files.append(image_file)

    return image_files


@pytest.fixture
def image_urls(image_types: set[str], faker: Faker, mock_response: aioresponses) -> list[ImageURL]:
    image_urls: list[ImageURL] = []

    for _ in range(faker.random_int(3, 5)):
        size = (faker.random_int(100, 300), faker.random_int(100, 300))
        image_bytes = faker.image(size=size, image_format=choice(["jpeg", "png"]))
        img = Image.open(BytesIO(image_bytes))
        url = faker.url()

        mock_response.get(url, repeat=True, callback=lambda *_, **__: CallbackResult(method="GET", body=image_bytes),)
        image_url = ImageURL(
            url=url,
            type=choice(list(image_types)),
            mime=img.get_format_mimetype(),
            height=img.height,
            width=img.width
        )
        image_urls.append(image_url)

    return image_urls
