from io import BytesIO
from random import choice

import mutagen.id3
import numpy
import pytest
from PIL import Image
from aioresponses import aioresponses, CallbackResult
from faker import Faker

from musify.exception import MusifyValueError
from musify.model import MusifyModel
# noinspection PyProtectedMember
from musify.model.properties.image import ImageLink, HasImages, PICTURE_TYPES, \
    get_picture_name_from_id3_value, get_picture_id3_value_from_name
from tests.model.testers import MusifyModelTester
from tests.utils import assert_validator_skips


def test_get_picture_name_from_id3_value() -> None:
    assert get_picture_name_from_id3_value(mutagen.id3.PictureType.COVER_FRONT) == "Cover Front"
    assert get_picture_name_from_id3_value(mutagen.id3.PictureType.COVER_BACK) == "Cover Back"
    assert get_picture_name_from_id3_value(mutagen.id3.PictureType.BAND) == "Band"

    with pytest.raises(MusifyValueError):
        get_picture_name_from_id3_value(max(PICTURE_TYPES.values()) + 5)


def test_get_picture_id3_value_from_name() -> None:
    assert get_picture_id3_value_from_name("COVER_FRONT") == mutagen.id3.PictureType.COVER_FRONT
    assert get_picture_id3_value_from_name("Cover Back") == mutagen.id3.PictureType.COVER_BACK
    assert get_picture_id3_value_from_name("Other FILE icon") == mutagen.id3.PictureType.OTHER_FILE_ICON

    with pytest.raises(MusifyValueError):
        get_picture_id3_value_from_name("Invalid Picture Type")


class TestImageLink(MusifyModelTester):
    @pytest.fixture
    def model(self, faker: Faker) -> MusifyModel:
        # noinspection PyProtectedMember
        return ImageLink(
            url=faker.url(),
            height=faker.random_int(min=600, max=1000),
            width=faker.random_int(min=600, max=1000),
        )

    def test_equality(self, model: ImageLink, faker: Faker) -> None:
        assert model == model
        assert model == ImageLink(url=model.url, height=faker.random_int(), width=faker.random_int())

    def test_rich_comparison_dunder_methods(self, model: ImageLink, faker: Faker) -> None:
        assert model < ImageLink(url=faker.url(), height=model.height + 100, width=model.width + 100)
        assert model <= ImageLink(url=faker.url(), height=model.height + 100, width=model.width)
        assert model <= ImageLink(url=faker.url(), height=model.height, width=model.width)

        assert model > ImageLink(url=faker.url(), height=model.height - 100, width=model.width - 100)
        assert model >= ImageLink(url=faker.url(), height=model.height - 100, width=model.width,)
        assert model >= ImageLink(url=faker.url(), height=model.height, width=model.width)

    async def test_load(self, model: ImageLink, mock_response: aioresponses) -> None:
        body = BytesIO()
        img_array = numpy.random.rand(100, 100, 3) * 255
        img = Image.fromarray(img_array.astype("uint8")).convert("RGBA")
        img.save(body, format="PNG")

        mock_response.get(
            model.url,
            callback=lambda *_, **__: CallbackResult(method="GET", body=body.getvalue()),
        )
        assert (await model.load()).tobytes() == img.tobytes()


class TestHasImages(MusifyModelTester):
    @pytest.fixture
    def model(self, images: list[bytes], faker: Faker) -> MusifyModel:
        types = list(PICTURE_TYPES.keys())
        images = {choice(types): Image.open(BytesIO(img)) for img in images}
        links = {choice(types): ImageLink(url=faker.url()) for _ in range(faker.random_int(3, 6))}
        return HasImages(images=images | links)

    def test_deserialize_images_from_bytes(self, images: list[bytes]):
        # check default image type is assigned
        data = choice(images)
        result = HasImages._deserialize_images_from_bytes(data)
        assert result == {"Cover Front": Image.open(BytesIO(data))}

    def test_deserialize_images_from_bytes_mapping(self, images: list[bytes]):
        types = [
            choice((name, enum)) for name, enum in vars(mutagen.id3.PictureType).items()
            if isinstance(enum, mutagen.id3.PictureType)
        ]
        value = dict(zip(types, images))
        result = HasImages._deserialize_images_from_bytes(value)
        assert result == {kind: Image.open(BytesIO(img)) for kind, img in value.items()}

    def test_deserialize_images_from_bytes_skips(self, faker: Faker):
        assert_validator_skips(HasImages._deserialize_images_from_bytes, None)
        assert_validator_skips(HasImages._deserialize_images_from_bytes, faker.pystr())
        assert_validator_skips(HasImages._deserialize_images_from_bytes, faker.pyint())
        assert_validator_skips(HasImages._deserialize_images_from_bytes, faker.pytuple())
        assert_validator_skips(HasImages._deserialize_images_from_bytes, faker.pylist())

    def test_convert_id3_value_to_picture_type_name(self, images: list[bytes]):
        types = [
            choice((enum, int(enum))) for enum in vars(mutagen.id3.PictureType).values()
            if isinstance(enum, mutagen.id3.PictureType)
        ]
        value = dict(zip(types, images))
        result = HasImages._convert_id3_value_to_picture_type_name(value)
        assert result == {get_picture_name_from_id3_value(kind): img for kind, img in value.items()}

    def test_convert_id3_value_to_picture_type_name_skips(self, faker: Faker):
        assert_validator_skips(HasImages._convert_id3_value_to_picture_type_name, None)
        assert_validator_skips(HasImages._convert_id3_value_to_picture_type_name, faker.pystr())
        assert_validator_skips(HasImages._convert_id3_value_to_picture_type_name, faker.pyint())
        assert_validator_skips(HasImages._convert_id3_value_to_picture_type_name, faker.pytuple())
        assert_validator_skips(HasImages._convert_id3_value_to_picture_type_name, faker.pylist())

    def test_serialize_images(
            self, model: HasImages, faker: Faker, mock_response: aioresponses
    ):
        for image in model.images.values():
            if not isinstance(image, ImageLink):
                continue

            image_bytes = faker.image()
            mock_response.get(image.url, callback=lambda *_, **__: CallbackResult(method="GET", body=image_bytes))

        result = model.model_dump(include={"images"})["images"]
        assert list(result) == list(model.images)
        assert all(isinstance(img, bytes) for img in result.values())
