from typing import Any

from faker import Faker
from yarl import URL

IMAGE_SIZES: tuple[int, ...] = tuple([64, 160, 300, 320, 500, 640, 800, 1000])


def generate_images(faker: Faker) -> list[dict[str, Any]]:
    """Return a list of randomly generated Spotify API responses for an image."""
    def generate_image(size: int = faker.random_element(IMAGE_SIZES)):
        """Return a randomly generated Spotify API response for an image."""
        url = URL.build(scheme="http", host="i.scdn.co", path=f"/image/{faker.pystr(40, 40)}")
        return {"url": str(url), "height": size, "width": size}

    images = [generate_image(size) for size in faker.random_elements(IMAGE_SIZES)]
    images.sort(key=lambda x: x["height"], reverse=True)
    return images
