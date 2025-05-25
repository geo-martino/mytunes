from contextlib import ExitStack
from io import BytesIO
from pathlib import Path
from random import choice
from unittest import mock

import mutagen.id3
import pytest
from PIL import Image
from aioresponses import aioresponses, CallbackResult
from faker import Faker

from musify.exception import MusifyValueError
from musify.model import MusifyModel
from musify.model.properties.image import ImageBase, ImageSource, ImageURL, HasImages, ImageFile
from tests.model.testers import MusifyModelTester


class TestImageBase(MusifyModelTester):
    @pytest.fixture
    def model(self, image_types: set[str], faker: Faker) -> MusifyModel:
        return ImageBase(
            type=image_types.pop(),
            height=faker.random_int(min=600, max=1000),
            width=faker.random_int(min=600, max=1000),
        )

    def test_rich_comparison_dunder_methods(self, model: ImageSource, image_types: set[str], faker: Faker) -> None:
        assert model < ImageBase(type=choice(list(image_types)), height=model.height + 100, width=model.width + 100)
        assert model <= ImageBase(type=choice(list(image_types)), height=model.height + 100, width=model.width)
        assert model <= ImageBase(type=choice(list(image_types)), height=model.height, width=model.width)

        assert model > ImageBase(type=choice(list(image_types)), height=model.height - 100, width=model.width - 100)
        assert model >= ImageBase(type=choice(list(image_types)), height=model.height - 100, width=model.width, )
        assert model >= ImageBase(type=choice(list(image_types)), height=model.height, width=model.width)

    def test_id3_type_property(self, model: ImageSource) -> None:
        model.type = "COVER_FRONT"
        assert model.id3_type == mutagen.id3.PictureType.COVER_FRONT
        model.type = "ARTIST"
        assert model.id3_type == mutagen.id3.PictureType.ARTIST
        model.type = "OTHER_FILE_ICON"
        assert model.id3_type == mutagen.id3.PictureType.OTHER_FILE_ICON

    def test_get_type_from_number(self):
        assert ImageSource._get_type_from_number(3) == "COVER_FRONT"
        assert ImageSource._get_type_from_number(8) == "ARTIST"
        assert ImageSource._get_type_from_number(2) == "OTHER_FILE_ICON"
        assert ImageSource._get_type_from_number("This will be skipped") == "This will be skipped"

        with pytest.raises(MusifyValueError):
            ImageSource._get_type_from_number(100)

    def test_validate_id3_type(self):
        assert ImageSource._validate_id3_type("COVER_FRONT") == "COVER_FRONT"
        assert ImageSource._validate_id3_type("ARTIST") == "ARTIST"
        assert ImageSource._validate_id3_type("OTHER_FILE_ICON") == "OTHER_FILE_ICON"

        with pytest.raises(MusifyValueError):
            ImageSource._validate_id3_type("This will fail")

    def test_update_attributes(self, model: ImageBase, images: list[bytes]) -> None:
        img_bytes = choice(images)
        img = Image.open(BytesIO(img_bytes))

        model.update_attributes(img)
        assert model.mime == img.get_format_mimetype()
        assert model.height == img.height
        assert model.width == img.width

    def test_from_image(self, images: list[bytes]) -> None:
        img_bytes = choice(images)
        img = Image.open(BytesIO(img_bytes))

        result = ImageBase.model_validate(img_bytes)
        assert result.mime == img.get_format_mimetype()
        assert result.height == img.height
        assert result.width == img.width

        result = ImageBase.model_validate(img)
        assert result.mime == img.get_format_mimetype()
        assert result.height == img.height
        assert result.width == img.width


class TestImageFile(MusifyModelTester):
    @pytest.fixture
    def model(self, image_types: set[str], faker: Faker, tmp_path: Path) -> MusifyModel:
        return ImageFile(
            path=tmp_path.joinpath(faker.file_name(category="image")),
            type=choice(list(image_types)),
            height=faker.random_int(min=600, max=1000),
            width=faker.random_int(min=600, max=1000),
        )

    def test_equality(self, model: ImageFile, image_types: set[str], faker: Faker) -> None:
        assert model == model
        assert model == ImageFile(
            path=model.path,
            type=model.type,
            height=faker.random_int(),
            width=faker.random_int()
        )

        assert model != ImageFile(
            path=faker.file_path(extension="jpg"),
            type=model.type,
            height=faker.random_int(),
            width=faker.random_int()
        )
        assert model != ImageFile(
            path=model.path,
            type=next(t for t in image_types if t != model.type),
            height=faker.random_int(),
            width=faker.random_int()
        )

    async def test_load(self, model: ImageFile, faker: Faker, tmp_path: Path) -> None:
        assert model.path.is_relative_to(tmp_path)

        size = (faker.random_int(100, 300), faker.random_int(100, 300))
        image_bytes = faker.image(size=size, image_format=choice(["jpeg", "png"]))

        model.path.parent.mkdir(parents=True, exist_ok=True)
        model.path.write_bytes(image_bytes)

        assert await model.load() == Image.open(BytesIO(image_bytes))


class TestImageURL(MusifyModelTester):
    @pytest.fixture
    def model(self, faker: Faker) -> MusifyModel:
        return ImageURL(
            url=faker.url(),
            height=faker.random_int(min=600, max=1000),
            width=faker.random_int(min=600, max=1000),
        )

    def test_equality(self, model: ImageURL, image_types: set[str], faker: Faker) -> None:
        assert model == model
        assert model == ImageURL(
            url=model.url,
            type=model.type,
            height=faker.random_int(),
            width=faker.random_int()
        )

        assert model != ImageURL(
            url=faker.url(),
            type=model.type,
            height=faker.random_int(),
            width=faker.random_int()
        )
        assert model != ImageURL(
            url=model.url,
            type=next(t for t in image_types if t != model.type),
            height=faker.random_int(),
            width=faker.random_int()
        )

    async def test_load(self, model: ImageURL, faker: Faker, mock_response: aioresponses) -> None:
        img = faker.image()
        mock_response.get(
            model.url,
            callback=lambda *_, **__: CallbackResult(method="GET", body=img),
        )

        assert await model.load() == Image.open(BytesIO(img))


class TestHasImages(MusifyModelTester):
    @pytest.fixture
    def model(self, image_files: list[ImageFile], image_urls: list[ImageURL]) -> MusifyModel:
        return HasImages(images={img.type: img for img in image_files + image_urls})

    async def test_load_images(self, model: HasImages, images: list[bytes], faker: Faker) -> None:
        update_attributes = choice([True, False])
        kwargs = faker.pydict()
        img = Image.open(BytesIO(images[0]))

        classes = {m.__class__ for m in model.images.values()}
        mocked_load = (
            mock.patch.object(cls, "load", return_value=img, new_callable=mock.AsyncMock,)
            for cls in classes
        )
        mocked_update = (
            mock.patch.object(cls, "update_attributes")
            for cls in classes
        )

        with ExitStack() as stack:
            mocked_load = [stack.enter_context(m) for m in mocked_load]
            mocked_update = [stack.enter_context(m) for m in mocked_update]

            await model.load_images(update_attributes, **kwargs)

            assert sum(m.call_count for m in mocked_load) == len(model.images)
            assert sum(m.call_count for m in mocked_update) == len(model.images) * update_attributes

            for mock_load, mock_update in zip(mocked_load, mocked_update):
                for call in mock_load.mock_calls:
                    assert call.kwargs == kwargs
                for call in mock_update.mock_calls:
                    assert call.args == (img,)
