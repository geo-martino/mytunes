from copy import deepcopy
from http import HTTPMethod
from random import choice

import pytest

from musify.libraries.remote.spotify.api import SpotifyAPI
from musify.libraries.remote.spotify.api.cache import SpotifyRepositorySettings, SpotifyPaginatedRepositorySettings
from tests.libraries.remote.spotify.api.mock import SpotifyMock


class TestSpotifyRequestSettings:

    @pytest.fixture(scope="class")
    def settings(self) -> SpotifyRepositorySettings:
        """Yields a :py:class:`SpotifyRequestSettings` object as a pytest.fixture."""
        return SpotifyRepositorySettings(name="test")

    def test_core_getters(self, settings: SpotifyRepositorySettings, api_mock: SpotifyMock):
        for responses in api_mock.item_type_map.values():
            response = deepcopy(choice(responses))
            name = response["display_name"] if response["type"] == "user" else response["name"]
            assert settings.get_name(response) == name
            assert settings.get_key(method=HTTPMethod.GET, url=response["href"]) == (response["id"],)
            assert settings.get_key(method="GET", url=response["href"]) == (response["id"],)

            # does not store post requests
            assert settings.get_key(method=HTTPMethod.POST, url=response["href"]) == (None,)

        response = deepcopy(choice(api_mock.user_tracks))
        assert settings.get_name(response) is None

        url = f"{api_mock.url_api}/me/tracks"
        assert settings.get_key(method=HTTPMethod.GET, url=url) == (None,)

    @pytest.fixture(scope="class")
    def settings_paginated(self) -> SpotifyPaginatedRepositorySettings:
        """Yields a :py:class:`SpotifyPaginatedRequestSettings` object as a pytest.fixture."""
        return SpotifyPaginatedRepositorySettings(name="test")

    def test_paginated_getters(
            self,
            settings_paginated: SpotifyPaginatedRepositorySettings,
            api: SpotifyAPI,
            api_mock: SpotifyMock
    ):
        for parent, child in api.collection_item_map.items():
            response = choice(api_mock.item_type_map[parent])[child.name.lower() + "s"]
            url = response["href"]
            assert settings_paginated.get_offset(url) == response["offset"]
            assert settings_paginated.get_limit(url) == response["limit"]

        url = f"{api_mock.url_api}/me/tracks"
        assert settings_paginated.get_offset(url) == 0
        assert settings_paginated.get_limit(url) == 50
