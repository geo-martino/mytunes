from collections.abc import Generator
from contextlib import contextmanager, asynccontextmanager
from io import BytesIO
from unittest.mock import Mock, patch, AsyncMock, MagicMock

import pytest
from PIL import Image, ImageFile as PILImageFile
from aiohttp import ClientSession, ClientResponse
from aiorequestful.request import RequestHandler
from faker import Faker
from yarl import URL

from musify.models.exception import RequestError
from musify.models.properties.image import ImageURL, ImageFile
from musify.spotify import API_URL
# noinspection PyProtectedMember
from musify.spotify.api._playlist import _SpotifySavedPlaylistEndpoints
from musify.spotify.collection.playlist import SpotifyPlaylist
from musify.spotify.properties.uri import SpotifyResourceURI
from tests.models.api.testers import EndpointsTester


class TestSpotifySavedPlaylistEndpoints(EndpointsTester):
    @pytest.fixture
    def model(self, handler: RequestHandler) -> _SpotifySavedPlaylistEndpoints:
        return _SpotifySavedPlaylistEndpoints.model_validate(handler)

    @pytest.fixture
    def uri(self, faker: Faker) -> SpotifyResourceURI:
        return SpotifyResourceURI.from_id(faker.pystr(22, 22), kind=SpotifyPlaylist.type)

    async def test_format_body_params(self, model: _SpotifySavedPlaylistEndpoints, faker: Faker):
        name = faker.name()
        description = faker.sentence()
        public = faker.boolean()
        collaborative = faker.boolean() if not public else False

        assert model._format_playlist_body(name=name) == {"name": name}
        assert model._format_playlist_body(description=description) == {"description": description}

        assert model._format_playlist_body(collaborative=collaborative, public=public) == {
            "collaborative": collaborative,
            "public": public,
        }

        assert model._format_playlist_body(
            name=name, description=description, collaborative=collaborative, public=public
        ) == {
            "name": name,
            "description": description,
            "collaborative": collaborative,
            "public": public,
        }

    async def test_format_body_params_fails(self, model: _SpotifySavedPlaylistEndpoints):
        with pytest.raises(RequestError, match="cannot be both public and collaborative"):
            model._format_playlist_body(public=True, collaborative=True)

    @pytest.fixture
    def mock_put(self, handler: RequestHandler) -> Generator[Mock, None, None]:
        with patch.object(RequestHandler, "put") as mock_put:
            yield mock_put

    async def test_modify_images(
            self,
            model: _SpotifySavedPlaylistEndpoints,
            uri: SpotifyResourceURI,
            image_object: PILImageFile,
            mock_put: Mock,
            faker: Faker,
    ):
        expected_url = uri.api_url.joinpath("images")
        expected_mime = Image.MIME[image_object.format]

        data = BytesIO()
        image_object.save(data, format=image_object.format)
        expected_data = data.getvalue()

        await model.modify(str(uri.api_url), image=image_object)
        mock_put.assert_called_once_with(
            expected_url, data=expected_data, headers={"Content-Type": expected_mime}
        )
