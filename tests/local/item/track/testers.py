from abc import ABCMeta, abstractmethod
from argparse import Namespace
from io import BytesIO
from random import choice
from typing import Any
from unittest import mock

import mutagen
import pytest
from PIL import Image
from PIL.ImageFile import ImageFile as PILImageFile

from musify.local.exception import FileError
from musify.local.item.track import LocalTrack, TagDumpContext
from musify.models.properties.image import ImageFile
from tests.models.testers import MusifyModelTester, UniqueKeyTester


class LocalTrackEmbeddedImageTester(MusifyModelTester, metaclass=ABCMeta):

    @abstractmethod
    def test_get_bytes(self, pictures: dict[str, Any]):
        raise NotImplementedError

    @staticmethod
    def test_from_tag_value(model: LocalTrack.EmbeddedImage, pictures: dict[str, Any]):
        kind, picture = choice(list(pictures.items()))
        image = Image.open(BytesIO(model._get_bytes(picture)))
        assert model.model_validate(picture) == model.__class__(
            type=kind,
            mime=image.get_format_mimetype(),
            height=image.height,
            width=image.width,
        )

    @staticmethod
    def test_from_image_model(model: LocalTrack.EmbeddedImage, image_files: list[ImageFile]):
        other = choice(image_files)
        model = model.__class__.from_image_model(other)
        assert model.type == other.type
        assert model.mime == other.mime
        assert model.height == other.height
        assert model.width == other.width

    @staticmethod
    async def test_get_file(model: LocalTrack.EmbeddedImage):
        file = mutagen.FileType()
        file.filename = str(model.path)
        assert await model._get_file(file) is file  # doesn't change file when given

        with mock.patch.object(LocalTrack, "load_file", return_value=file) as mocked_get_bytes:
            assert await model._get_file() is file
            mocked_get_bytes.assert_called_once_with(model.path)

    @staticmethod
    async def test_get_file_fails(model: LocalTrack.EmbeddedImage):
        file = mutagen.FileType()
        with pytest.raises(FileError, match="file does not match the path"):
            await model._get_file(file)

        model.path = None
        with pytest.raises(FileError, match="Path is not set"):
            await model._get_file()

    @staticmethod
    def test_get_image_bytes(model: LocalTrack.EmbeddedImage, image_bytes: list[bytes], image_objects: list[PILImageFile]):
        img_bytes, img_obj = choice(list(zip(image_bytes, image_objects)))
        assert model._get_image_data(img_bytes) == (img_obj, img_bytes)
        # PIL appears to modify the image bytes so we can only check the first part
        assert model._get_image_data(img_obj)[0] == img_obj

    @staticmethod
    def test_get_id3_type_from_tag(model: LocalTrack.EmbeddedImage, pictures: dict[str, Any]):
        with mock.patch.object(model.__class__, "_get_type_from_number", return_value="test_type") as mocked_get_type:
            attr = next(iter(pictures.values()))
            assert model.__class__.get_id3_type_from_tag(attr) == mocked_get_type.return_value

    @staticmethod
    def test_from_tag(model: LocalTrack.EmbeddedImage, pictures: dict[str, Any]):
        kind, tag_value = choice(list(pictures.items()))
        img = Image.open(BytesIO(model.__class__._get_bytes(tag_value)))

        assert model.__class__.model_validate(tag_value) == model.__class__(
            type=kind, mime=img.get_format_mimetype(), height=img.height, width=img.width,
        )
        assert model.__class__.model_validate(model.__class__._get_bytes(tag_value)) == model.__class__(
            mime=img.get_format_mimetype(), height=img.height, width=img.width,
        )
        assert model.__class__.model_validate(img) == model.__class__(
            mime=img.get_format_mimetype(), height=img.height, width=img.width,
        )

    async def test_build(self, model: LocalTrack.EmbeddedImage, pictures: dict[str, Any]):
        assert model.build(None) is None

        expected = next(
            (pic for pic in pictures.values() if model.get_id3_type_from_tag(pic) == model.type),
            next(iter(pictures.values()))
        )
        value = model._get_bytes(expected)
        result = model.build(choice([value, Image.open(BytesIO(value))]))
        # PIL appears to modify the image bytes so we can't check the bytes directly
        assert isinstance(result, expected.__class__)


class LocalTrackTester(UniqueKeyTester):
    @staticmethod
    def test_map_images(model: LocalTrack, pictures: dict[str, Any]):
        assert model._map_images(list(pictures.values())) == pictures

    @staticmethod
    def test_serialize_images(model: LocalTrack, image_bytes: list[bytes], image_objects: list[PILImageFile], pictures: dict[str, Any]):
        model.images = pictures

        image_model = model.EmbeddedImage(mime="image/png", height=100, width=100)
        loaded_images = {kind: choice(image_objects) for kind in model.images}
        context = Namespace(by_alias=True, context=TagDumpContext(loaded_images=loaded_images))
        assert loaded_images

        with (
            mock.patch.object(
                model.EmbeddedImage, "from_image_model", return_value=image_model
            ) as mocked_from_image_model,
            mock.patch.object(model.EmbeddedImage, "build") as mocked_build,
        ):
            # noinspection PyTypeChecker
            result = model._serialize_images(image_bytes, info=context)
            assert len(result) == len(loaded_images)

            for kind, image in loaded_images.items():
                mocked_from_image_model.assert_any_call(model.images[kind])
                mocked_build.assert_any_call(image)
