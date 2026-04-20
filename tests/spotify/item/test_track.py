import pytest
from faker import Faker

from mytunes.properties.audio import Decibels
from mytunes.properties.length import Length
from mytunes.properties.music import KeySignature
from mytunes.spotify import API_URL
# noinspection PyProtectedMember
from mytunes.spotify._item.track import SpotifyTrack, SpotifyAudioFeatures, SpotifyAudioAnalysis, \
    _SpotifyAudioAnalysisMeta, _SpotifyAudioAnalysisTrack
from mytunes.spotify.exception import SpotifyError
from tests.spotify.generator import SpotifyPayloadGenerator
from tests.spotify.testers import SpotifyResourceTester, SpotifyModelTester


class TestSpotifyTrack(SpotifyResourceTester):
    @pytest.fixture
    def model(self, generator: SpotifyPayloadGenerator, faker: Faker) -> SpotifyTrack:
        return SpotifyTrack(
            name=faker.name(),
            uri=generator.generate_uri("track"),
        )

    def test_response(self, generator: SpotifyPayloadGenerator):
        payload = generator.generate_track()
        generator.add_track_extended_properties(payload)

        model = SpotifyTrack.model_validate(payload)

        self.assert_expected_name(model, payload)
        self.assert_expected_identifiers(model, payload)
        self.assert_expected_images(model, payload)
        self.assert_expected_artists(model, payload)
        self.assert_expected_length(model, payload)
        self.assert_expected_rating(model, payload)

        assert model.disc.number == payload["disc_number"]
        assert model.track.number == payload["track_number"]
        assert model.track.total == payload["album"]["total_tracks"]

    def test_enrich_with_audio_features_fails(self, generator: SpotifyPayloadGenerator):
        payload = generator.generate_track()
        model = SpotifyTrack.model_validate(payload)

        audio_features_payload = generator.generate_audio_features()
        while audio_features_payload["uri"] == payload["uri"]:
            audio_features_payload = generator.generate_audio_features()

        audio_features = SpotifyAudioFeatures.model_validate(audio_features_payload)
        with pytest.raises(SpotifyError):
            model.enrich_with_audio_features(audio_features)

    def test_enrich_with_audio_features(self, generator: SpotifyPayloadGenerator):
        payload = generator.generate_track()
        model = SpotifyTrack.model_validate(payload)

        audio_features_payload = generator.generate_audio_features()
        audio_features_payload["uri"] = model.uri
        audio_features = SpotifyAudioFeatures.model_validate(audio_features_payload)

        model.enrich_with_audio_features(audio_features)
        assert model.key == audio_features.key
        assert model.bpm == audio_features.bpm


class TestSpotifyAudioFeatures(SpotifyResourceTester):
    @pytest.fixture
    def model(self, generator: SpotifyPayloadGenerator, faker: Faker) -> SpotifyAudioFeatures:
        resource_id = generator.generate_resource_id()
        return SpotifyAudioFeatures(
            analysis_url=API_URL.joinpath("audio-analysis", resource_id),
            uri=generator.generate_uri("track", resource_id),

            length=Length(faker.random_int(0, 10000) / 1000),
            bpm=faker.random_int(0, 300000) / 1000,
            time_signature=faker.random_int(3, 7),
            loudness=faker.random_int(-60000, 0) / 1000,

            acousticness=faker.random_int(0, 1000) / 1000,
            danceability=faker.random_int(0, 1000) / 1000,
            energy=faker.random_int(0, 1000) / 1000,
            instrumentalness=faker.random_int(0, 1000) / 1000,
            liveness=faker.random_int(0, 1000) / 1000,
            speechiness=faker.random_int(0, 1000) / 1000,
            valence=faker.random_int(0, 1000) / 1000,
        )

    def test_response(self, generator: SpotifyPayloadGenerator):
        payload = generator.generate_audio_features()

        model = SpotifyAudioFeatures.model_validate(payload)

        assert model.analysis_url == payload["analysis_url"]
        assert model.uri == payload["uri"]

        assert float(model.length) == payload["duration_ms"] / 1000
        assert model.bpm == payload["tempo"]
        assert model.time_signature == payload["time_signature"]
        assert model.loudness == payload["loudness"]

        assert model.acousticness == payload["acousticness"]
        assert model.danceability == payload["danceability"]
        assert model.energy == payload["energy"]
        assert model.instrumentalness == payload["instrumentalness"]
        assert model.liveness == payload["liveness"]
        assert model.speechiness == payload["speechiness"]
        assert model.valence == payload["valence"]


class TestSpotifyAudioAnalysis(SpotifyModelTester):
    @pytest.fixture
    def model(self, generator: SpotifyPayloadGenerator, faker: Faker) -> SpotifyAudioAnalysis:
        return SpotifyAudioAnalysis(
            meta=_SpotifyAudioAnalysisMeta(
                analyzer_version=".".join(tuple(str(faker.random_int(100, 999)))),
                platform=faker.random_element((
                    faker.windows_platform_token(),
                    faker.mac_platform_token(),
                    faker.linux_platform_token(),
                    faker.ios_platform_token(),
                    faker.android_platform_token(),
                )),
                detailed_status=faker.word(),
                status_code=faker.random_int(0, 1),
                timestamp=faker.past_datetime(),
                analysis_time=Length(faker.random_int(0, 10000) / 1000),
                input_process=faker.sentence(),
            ),
            track=_SpotifyAudioAnalysisTrack(
                num_samples=faker.random_int(0, 1000000),
                length=Length(faker.random_int(0, 10000) / 1000),
                sample_md5=faker.md5(),
                offset_seconds=Length(faker.random_int(0, 10000) / 1000),
                window_seconds=Length(faker.random_int(0, 10000) / 1000),
                analysis_sample_rate=faker.random_int(22050, 96000),
                analysis_channels=faker.random_int(1, 2),
                end_of_fade_in=Length(faker.random_int(0, 10000) / 1000),
                start_of_fade_out=Length(faker.random_int(0, 10000) / 1000),
                loudness=Decibels(faker.random_int(-60000, 0) / 1000),
                bpm=faker.random_int(0, 300000) / 1000,
                bpm_confidence=faker.random_int(0, 1000) / 1000,
                time_signature=faker.random_int(3, 7),
                time_signature_confidence=faker.random_int(0, 1000) / 1000,
                key=KeySignature(root=faker.random_int(0, 11), mode=faker.random_int(0, 1)),
                key_confidence=faker.random_int(0, 1000) / 1000,
                mode_confidence=faker.random_int(0, 1000) / 1000,
                codestring=faker.md5(),
                code_version=faker.random_int(1, 1000) / 100,
                echoprintstring=faker.md5(),
                echoprint_version=faker.random_int(1, 1000) / 100,
                synchstring=faker.md5(),
                synch_version=faker.random_int(1, 1000) / 100,
                rhythmstring=faker.md5(),
                rhythm_version=faker.random_int(1, 1000) / 100,
            ),
            bars=[generator.generate_audio_analysis_interval() for _ in range(faker.random_int(1, 10))],
            beats=[generator.generate_audio_analysis_interval() for _ in range(faker.random_int(1, 10))],
            sections=[generator.generate_audio_analysis_section() for _ in range(faker.random_int(1, 10))],
            segments=[generator.generate_audio_analysis_segment() for _ in range(faker.random_int(1, 10))],
            tatums=[generator.generate_audio_analysis_interval() for _ in range(faker.random_int(1, 10))],
        )

    def test_response(self, generator: SpotifyPayloadGenerator):
        payload = generator.generate_audio_analysis()

        # just check if it validates, this one is too big to check every field...
        SpotifyAudioAnalysis.model_validate(payload)
