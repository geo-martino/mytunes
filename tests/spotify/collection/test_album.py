import pytest
from faker import Faker
from yarl import URL

from mytunes.properties.date import SparseDate
from mytunes.spotify._collection.album import SpotifyAlbumCollection
from mytunes.spotify.cursors import SpotifyIndexCursor
from tests.spotify.generator import SpotifyPayloadGenerator
from tests.spotify.testers import SpotifyResourceTester


class TestSpotifyAlbumCollection(SpotifyResourceTester):
    @pytest.fixture
    def model(self, generator: SpotifyPayloadGenerator, faker: Faker) -> SpotifyAlbumCollection:
        kind = "album"
        album_id = generator.generate_resource_id()

        return SpotifyAlbumCollection(
            name=faker.name(),
            rating=faker.random_int(0, 100),
            uri=generator.generate_uri(kind, album_id),
            cursor=SpotifyIndexCursor(
                url=URL(generator.generate_href(kind, album_id)).joinpath("tracks"),
                limit=20,
                offset=0,
                total=faker.random_int(),
            ),
            released_at=SparseDate.model_validate(faker.date()),
            compilation=faker.boolean(),
        )

    def test_response(self, generator: SpotifyPayloadGenerator):
        payload = generator.generate_album()
        generator.add_album_artists(payload)
        generator.add_album_extended_properties(payload)
        generator.add_album_tracks(payload)

        model = SpotifyAlbumCollection.model_validate(payload)

        self.assert_expected_name(model, payload)
        self.assert_expected_identifiers(model, payload)
        self.assert_expected_images(model, payload)
        self.assert_expected_genres(model, payload)
        self.assert_expected_rating(model, payload)

        self.assert_has_all_items(model, payload["tracks"]["items"], payload["tracks"]["total"])

        assert model.disc_total == max(track["disc_number"] for track in payload["tracks"]["items"])
        assert model.compilation is (payload["album_type"] == "compilation")

        for track in model.tracks:
            assert track.released_at == model.released_at
            assert track.track.total == model.track_total
            assert track.disc.total == model.disc_total
