from collections.abc import Generator
from io import BytesIO
from unittest.mock import Mock, patch

import pytest
from PIL import Image, ImageFile as PILImageFile
from aiorequestful.request import RequestHandler
from faker import Faker

from mytunes import PROGRAM_NAME
from mytunes.exception import RequestError
# noinspection PyProtectedMember
from mytunes.spotify._api.playlist import _SpotifyPlaylistLibraryEndpoints
from mytunes.spotify._collection.playlist import SpotifyPlaylist
from mytunes.spotify._properties.uri import SpotifyResourceURI
from tests.testers import EndpointsTester


class TestSpotifyPlaylistLibraryEndpoints(EndpointsTester):
    @pytest.fixture
    def model(self, handler: RequestHandler) -> _SpotifyPlaylistLibraryEndpoints:
        return _SpotifyPlaylistLibraryEndpoints.model_validate(handler)

    @pytest.fixture
    def uri(self, faker: Faker) -> SpotifyResourceURI:
        return SpotifyResourceURI.from_id(faker.pystr(22, 22), kind=SpotifyPlaylist.type)

    async def test_format_body_params(self, model: _SpotifyPlaylistLibraryEndpoints, faker: Faker):
        name = faker.name()
        description = faker.sentence()
        public = faker.boolean()
        collaborative = faker.boolean() if not public else False
        default_name = f"{PROGRAM_NAME} Playlist"

        assert await model._format_playlist_body(name=name) == {"name": name}
        assert await model._format_playlist_body(description=description) == {
            "name": default_name,
            "description": description
        }

        assert await model._format_playlist_body(collaborative=collaborative, public=public) == {
            "name": default_name,
            "collaborative": collaborative,
            "public": public,
        }

        assert await model._format_playlist_body(
            name=name, description=description, collaborative=collaborative, public=public
        ) == {
            "name": name,
            "description": description,
            "collaborative": collaborative,
            "public": public,
        }

    async def test_format_body_params_fails(self, model: _SpotifyPlaylistLibraryEndpoints):
        with pytest.raises(RequestError, match="cannot be both public and collaborative"):
            await model._format_playlist_body(public=True, collaborative=True)

    @pytest.fixture
    def mock_put(self, handler: RequestHandler) -> Generator[Mock]:
        with patch.object(RequestHandler, "put") as mock_put:
            yield mock_put

    async def test_modify_images(
            self,
            model: _SpotifyPlaylistLibraryEndpoints,
            uri: SpotifyResourceURI,
            image_object: PILImageFile.ImageFile,
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
