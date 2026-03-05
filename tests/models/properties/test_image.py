from contextlib import ExitStack
from pathlib import Path
from random import choice
from unittest import mock
from unittest.mock import patch

import mutagen.id3
import pytest
from PIL.ImageFile import ImageFile as PILImageFile
from aioresponses import aioresponses, CallbackResult
from faker import Faker

from musify.exception import MusifyValueError
from musify.models.properties.image import ImageBase, ImageSource, ImageURL, HasImages, ImageFile
from tests.models.testers import MusifyModelTester


class TestImageBase(MusifyModelTester):
    @pytest.fixture
    def model(self, image_types: set[str], faker: Faker) -> ImageBase:
        return ImageBase(
            type=image_types.pop(),
            height=faker.random_int(min=600, max=1000),
            width=faker.random_int(min=600, max=1000),
        )

    def test_rich_comparison_dunder_methods(self, model: ImageSource, image_types: set[str], faker: Faker):
        assert model < ImageBase(type=choice(list(image_types)), height=model.height + 100, width=model.width + 100)
        assert model <= ImageBase(type=choice(list(image_types)), height=model.height + 100, width=model.width)
        assert model <= ImageBase(type=choice(list(image_types)), height=model.height, width=model.width)

        assert model > ImageBase(type=choice(list(image_types)), height=model.height - 100, width=model.width - 100)
        assert model >= ImageBase(type=choice(list(image_types)), height=model.height - 100, width=model.width, )
        assert model >= ImageBase(type=choice(list(image_types)), height=model.height, width=model.width)

    def test_id3_type_property(self, model: ImageSource):
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

    def test_update_attributes(self, model: ImageBase, image_object: PILImageFile):
        model.update_attributes(image_object)
        assert model.mime == image_object.get_format_mimetype()
        assert model.height == image_object.height
        assert model.width == image_object.width

    def test_from_image(self, image_bytes: list[bytes], image_objects: list[PILImageFile]):
        img_bytes, img_obj = choice(list(zip(image_bytes, image_objects)))

        result = ImageBase.model_validate(img_bytes)
        assert result.mime == img_obj.get_format_mimetype()
        assert result.height == img_obj.height
        assert result.width == img_obj.width

        result = ImageBase.model_validate(img_obj)
        assert result.mime == img_obj.get_format_mimetype()
        assert result.height == img_obj.height
        assert result.width == img_obj.width


class TestImageFile(MusifyModelTester):
    @pytest.fixture
    def model(self, image_type: str, faker: Faker, tmp_path: Path) -> ImageFile:
        return ImageFile(
            path=tmp_path.joinpath(faker.file_name(category="image")),
            type=image_type,
            height=faker.random_int(min=600, max=1000),
            width=faker.random_int(min=600, max=1000),
        )

    def test_equality(self, model: ImageFile, image_types: set[str], faker: Faker):
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

    async def test_load(
            self, model: ImageFile, image_bytes: list[bytes], image_objects: list[PILImageFile], tmp_path: Path
    ):
        assert model.path.is_relative_to(tmp_path)
        img_bytes, img_obj = choice(list(zip(image_bytes, image_objects)))

        model.path.parent.mkdir(parents=True, exist_ok=True)
        model.path.write_bytes(img_bytes)

        assert await model.load() == img_obj


class TestImageURL(MusifyModelTester):
    @pytest.fixture
    def model(self, faker: Faker) -> ImageURL:
        return ImageURL(
            url=faker.url(),
            height=faker.random_int(min=600, max=1000),
            width=faker.random_int(min=600, max=1000),
        )

    def test_equality(self, model: ImageURL, image_types: set[str], faker: Faker):
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

    async def test_load(
            self,
            model: ImageURL,
            image_bytes: list[bytes],
            image_objects: list[PILImageFile],
            mock_response: aioresponses
    ):
        img_bytes, img_obj = choice(list(zip(image_bytes, image_objects)))
        mock_response.get(
            model.url,
            callback=lambda *_, **__: CallbackResult(method="GET", body=img_bytes),
        )

        assert await model.load() == img_obj


class TestHasImages(MusifyModelTester):
    @pytest.fixture
    def model(self, image_files: list[ImageFile], image_urls: list[ImageURL]) -> HasImages:
        return HasImages(images={img.type: img for img in image_files + image_urls})

    async def test_load_images(self, model: HasImages, image_object: PILImageFile, faker: Faker):
        update_attributes = faker.boolean()
        kwargs = faker.pydict()

        classes = {m.__class__ for m in model.images.values()}
        mock_load = (
            patch.object(cls, "load", return_value=image_object, new_callable=mock.AsyncMock,)
            for cls in classes
        )
        mock_update = (
            patch.object(cls, "update_attributes")
            for cls in classes
        )

        # noinspection PyAbstractClass
        with ExitStack() as stack:
            mock_load = [stack.enter_context(m) for m in mock_load]
            mock_update = [stack.enter_context(m) for m in mock_update]

            await model.load_images(update_attributes, **kwargs)

            assert sum(m.call_count for m in mock_load) == len(model.images)
            assert sum(m.call_count for m in mock_update) == len(model.images) * update_attributes

            for mock_load, mock_update in zip(mock_load, mock_update):
                for call in mock_load.mock_calls:
                    assert call.kwargs == kwargs
                for call in mock_update.mock_calls:
                    assert call.args == (image_object,)
