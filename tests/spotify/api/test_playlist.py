import pytest
from aiohttp.web_protocol import RequestHandler
from faker import Faker

# noinspection PyProtectedMember
from musify.spotify.api._playlist import _SpotifySavedPlaylistEndpoints
from tests.models.testers import BaseModelTester


class TestSpotifySavedPlaylistEndpoints(BaseModelTester):
    @pytest.fixture
    def model(self, handler: RequestHandler) -> _SpotifySavedPlaylistEndpoints:
        return _SpotifySavedPlaylistEndpoints.model_validate(handler)

    async def test_format_body_params(self, model: _SpotifySavedPlaylistEndpoints, faker: Faker):
        name = faker.name()
        description = faker.sentence()
        collaborative = faker.boolean()
        public = faker.boolean()

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
