from datetime import datetime
from typing import final, ClassVar, Annotated

from pydantic import Field, AliasChoices, AliasPath, field_validator, PositiveFloat, PositiveInt
from pydantic_core.core_schema import FieldValidationInfo

from musify.exception import MusifyValueError
from musify.models import MusifyModel
from musify.models.properties.audio import Decibels
from musify.models.properties.length import Length, HasLength
from musify.models.properties.order import Position
from musify.models.url import HttpURL
from musify.remote.item.track import RemoteTrack
from musify.spotify._base import SpotifyResource, SpotifyModel
from musify.spotify.item.album import SpotifyAlbum
from musify.spotify.item.artist import SpotifyArtist
from musify.spotify.item.genre import SpotifyGenre
from musify.spotify.properties.images import HasSpotifyImages
from musify.spotify.properties.music import HasSpotifyKeySignature
from musify.spotify.properties.popularity import HasPopularity
from musify.spotify.properties.uri import SpotifyResourceURI


@final
class SpotifyTrack(
    RemoteTrack[SpotifyArtist, SpotifyAlbum, SpotifyGenre, SpotifyResourceURI],
    SpotifyResource[SpotifyResourceURI],
    HasSpotifyImages,
    HasPopularity,
):
    __final__ = True

    disc: Position | None = Field(
        description="The position of the disc in the album that this track is featured on.",
        default=None,
        validation_alias="disc_number",
    )
    track: Position | None = Field(
        description="The position of the track on the album that this track is featured on.",
        default=None,
        validation_alias="track_number",
    )
    length: Length | None = Field(
        description="The length of this track in seconds.",
        default=None,
        validation_alias=AliasChoices(
            AliasPath("duration_ms", "totalMilliseconds"), "duration_ms"
        ),
    )

    @field_validator("length", mode="before", check_fields=True)
    @classmethod
    def _convert_length_to_seconds[T](cls, duration_ms: T | int) -> T | float:
        if not isinstance(duration_ms, int | float):
            return duration_ms
        return int(duration_ms) / 1000


type IntervalFloat = Annotated[float, Field(ge=0.0, le=1.0)]


@final
class SpotifyAudioFeatures(SpotifyResource[SpotifyResourceURI], HasLength, HasSpotifyKeySignature):
    __final__ = True

    type: ClassVar[str] = "audio_features"

    analysis_url: HttpURL = Field(
        description="A URL to access the full audio analysis of this track. An access token is required to access this data.",
    )

    length: Length = Field(
        description="The length of the track in seconds.",
        validation_alias="duration_ms",
    )
    bpm: PositiveFloat | None = Field(
        description="The tempo of this track.",
        default=None,
        validation_alias="tempo",
    )
    time_signature: int = Field(
        description=(
            "An estimated time signature. The time signature (meter) is a notational convention to specify how many "
            "beats are in each bar (or measure). The time signature ranges from 3 to 7 indicating time signatures "
            "of '3/4', to '7/4'."
        ),
        ge=3,
        le=7,
    )
    loudness: Decibels = Field(
        description=(
            "The overall loudness of a track in decibels (dB). Loudness values are averaged across the entire "
            "track and are useful for comparing relative loudness of tracks. Loudness is the quality of a sound "
            "that is the primary psychological correlate of physical strength (amplitude). Values typically range "
            "between -60 and 0 db."
        ),
    )

    acousticness: IntervalFloat = Field(
        description=(
            "A confidence measure from 0.0 to 1.0 of whether the track is acoustic. "
            "1.0 represents high confidence the track is acoustic."
        ),
    )
    danceability: IntervalFloat = Field(
        description=(
            "Danceability describes how suitable a track is for dancing based on a combination of musical elements "
            "including tempo, rhythm stability, beat strength, and overall regularity. "
            "A value of 0.0 is least danceable and 1.0 is most danceable."
        ),
    )
    energy: IntervalFloat = Field(
        description=(
            "Energy is a measure from 0.0 to 1.0 and represents a perceptual measure of intensity and activity. "
            "Typically, energetic tracks feel fast, loud, and noisy. For example, death metal has high energy, "
            "while a Bach prelude scores low on the scale. Perceptual features contributing to this attribute "
            "include dynamic range, perceived loudness, timbre, onset rate, and general entropy."
        ),
    )
    instrumentalness: IntervalFloat = Field(
        description=(
            "Predicts whether a track contains no vocals. 'Ooh' and 'aah' sounds are treated as instrumental "
            "in this context. Rap or spoken word tracks are clearly 'vocal'. "
            "The closer the instrumentalness value is to 1.0, the greater likelihood the track contains "
            "no vocal content. Values above 0.5 are intended to represent instrumental tracks, but confidence is "
            "higher as the value approaches 1.0."
        ),
    )
    liveness: IntervalFloat = Field(
        description=(
            "Detects the presence of an audience in the recording. Higher liveness values represent an increased "
            "probability that the track was performed live. "
            "A value above 0.8 provides strong likelihood that the track is live."
        ),
    )
    speechiness: IntervalFloat = Field(
        description=(
            "Speechiness detects the presence of spoken words in a track. The more exclusively speech-like the "
            "recording (e.g. talk show, audio book, poetry), the closer to 1.0 the attribute value. "
            "Values above 0.66 describe tracks that are probably made entirely of spoken words. "
            "Values between 0.33 and 0.66 describe tracks that may contain both music and speech, either in "
            "sections or layered, including such cases as rap music. Values below 0.33 most likely represent "
            "music and other non-speech-like tracks."
        ),
    )
    valence: IntervalFloat = Field(
        description=(
            "A measure from 0.0 to 1.0 describing the musical positiveness conveyed by a track. "
            "Tracks with high valence sound more positive (e.g. happy, cheerful, euphoric), while tracks with "
            "low valence sound more negative (e.g. sad, depressed, angry)."
        ),
    )

    @field_validator("length", mode="before")
    @classmethod
    def _convert_duration[T](cls, length: T | int, info: FieldValidationInfo) -> float:
        if not isinstance(length, int):
            return length

        return length / 1000

    @field_validator("uri", mode="after", check_fields=True)
    @classmethod
    def _validate_uri_matches_type[T: SpotifyResourceURI](cls, uri: T) -> T:
        if uri is None or not isinstance(uri, SpotifyResourceURI):
            return uri

        expected_type = "track"
        if not uri.type == expected_type:
            raise MusifyValueError(f"URI type {uri.type!r} does not match expected type {expected_type!r}")
        return uri


class _SpotifyAudioAnalysisMeta(MusifyModel):
    analyzer_version: str = Field(
        description="The version of the Analyzer used to analyze this track.",
    )
    platform: str = Field(
        description="The platform used to read the track's audio data.",
    )
    detailed_status: str = Field(
        description="A detailed status code for this track. If analysis data is missing, this code may explain why."
    )
    status_code: int = Field(
        description="The return code of the analyzer process. 0 if successful, 1 if any errors occurred.",
        ge=0,
        le=1,
    )
    timestamp: datetime = Field(
        description="The Unix timestamp (in seconds) at which this track was analyzed.",
    )
    analysis_time: Length = Field(
        description="The amount of time taken to analyze this track.",
    )
    input_process: str = Field(
        description="The method used to read the track's audio data.",
    )


class _SpotifyAudioAnalysisTrack(HasLength, HasSpotifyKeySignature):
    num_samples: PositiveInt = Field(
        description="The exact number of audio samples analyzed from this track. See also analysis_sample_rate.",
    )
    length: Length = Field(
        description="The length of the track in seconds.",
        validation_alias="duration",
    )
    sample_md5: str = Field(
        description="The MD5 hash of the audio samples analyzed from this track.",
    )
    offset_seconds: Length = Field(
        description=(
            "An offset to the start of the region of the track that was analyzed. "
            "(As the entire track is analyzed, this should always be 0.)"
        ),
    )
    window_seconds: Length = Field(
        description=(
            "The length of the region of the track was analyzed, if a subset of the track was analyzed. "
            "(As the entire track is analyzed, this should always be 0.)"
        ),
    )
    analysis_sample_rate: PositiveInt = Field(
        description=(
            "The sample rate used to decode and analyze this track. "
            "May differ from the actual sample rate of this track available on Spotify."
        ),
    )
    analysis_channels: PositiveInt = Field(
        description=(
            "The number of channels used for analysis. "
            "If 1, all channels are summed together to mono before analysis."
        ),
    )
    end_of_fade_in: Length = Field(
        description=(
            "The time, in seconds, at which the track's fade-in period ends. "
            "If the track has no fade-in, this will be 0.0."
        ),
    )
    start_of_fade_out: Length = Field(
        description=(
            "The time, in seconds, at which the track's fade-out period starts. "
            "If the track has no fade-out, this should match the track's length."
        ),
    )

    loudness: Decibels = Field(
        description=(
            "The overall loudness of a track in decibels (dB). Loudness values are averaged across the entire "
            "track and are useful for comparing relative loudness of tracks. Loudness is the quality of a sound "
            "that is the primary psychological correlate of physical strength (amplitude). Values typically range "
            "between -60 and 0 db."
        ),
    )

    bpm: PositiveFloat | None = Field(
        description="The tempo of this track.",
        default=None,
        validation_alias="tempo",
    )
    bpm_confidence: IntervalFloat = Field(
        description="The confidence, from 0.0 to 1.0, of the reliability of the tempo.",
        validation_alias="tempo_confidence",
    )

    time_signature: int = Field(
        description=(
            "An estimated time signature. The time signature (meter) is a notational convention to specify how many "
            "beats are in each bar (or measure). The time signature ranges from 3 to 7 indicating time signatures "
            "of '3/4', to '7/4'."
        ),
        ge=3,
        le=7,
    )
    time_signature_confidence: IntervalFloat = Field(
        description="The confidence, from 0.0 to 1.0, of the reliability of the time_signature.",
    )

    key_confidence: IntervalFloat = Field(
        description="The confidence, from 0.0 to 1.0, of the reliability of the key.",
    )
    mode_confidence: IntervalFloat = Field(
        description="The confidence, from 0.0 to 1.0, of the reliability of the mode.",
    )

    codestring: str = Field(
        description="An Echo Nest Musical Fingerprint (ENMFP) codestring for this track.",
    )
    code_version: PositiveFloat = Field(
        description="A version number for the Echo Nest Musical Fingerprint format used in the codestring field.",
    )

    echoprintstring: str = Field(
        description="An EchoPrint codestring for this track.",
    )
    echoprint_version: PositiveFloat = Field(
        description="A version number for the EchoPrint format used in the echoprintstring field.",
    )

    synchstring: str = Field(
        description="An Echo Nest Synchronization string for this track.",
    )
    synch_version: PositiveFloat = Field(
        description="A version number for the Synchstring used in the synchstring field.",
    )

    rhythmstring: str = Field(
        description="A Rhythmstring for this track. The format of this string is similar to the Synchstring.",
    )
    rhythm_version: PositiveFloat = Field(
        description="A version number for the Rhythmstring used in the rhythmstring field.",
    )


class _SpotifyAudioAnalysisInterval(MusifyModel):
    start: Length = Field(
        description="The starting point (in seconds) of the time interval.",
    )
    duration: Length = Field(
        description="The duration (in seconds) of the time interval.",
    )
    confidence: IntervalFloat = Field(
        description="The confidence, from 0.0 to 1.0, of the reliability of the interval.",
    )


class _SpotifyAudioAnalysisSection(_SpotifyAudioAnalysisInterval, HasSpotifyKeySignature):
    loudness: float = Field(
        description=(
            "The overall loudness of the section in decibels (dB). Loudness values are useful for comparing "
            "relative loudness of sections within tracks."
        ),
        ge=-60.0,
        le=0.0,
    )

    bpm: PositiveFloat | None = Field(
        description=(
            "The overall estimated tempo of the section in beats per minute (BPM). In musical terminology, "
            "tempo is the speed or pace of a given piece and derives directly from the average beat duration."
        ),
        default=None,
        validation_alias="tempo",
    )
    bpm_confidence: IntervalFloat = Field(
        description=(
            "The confidence, from 0.0 to 1.0, of the reliability of the tempo. Some tracks contain tempo "
            "changes or sounds which don't contain tempo (like pure speech) which would correspond to a "
            "low value in this field."
        ),
        validation_alias="tempo_confidence",
    )

    time_signature: int = Field(
        description=(
            "An estimated time signature. The time signature (meter) is a notational convention to specify how many "
            "beats are in each bar (or measure). The time signature ranges from 3 to 7 indicating time signatures "
            "of '3/4', to '7/4'."
        ),
        ge=3,
        le=7,
    )
    time_signature_confidence: IntervalFloat = Field(
        description=(
            "The confidence, from 0.0 to 1.0, of the reliability of the time_signature. "
            "Sections with time signature changes may correspond to low values in this field."
        ),
    )

    key_confidence: IntervalFloat = Field(
        description=(
            "The confidence, from 0.0 to 1.0, of the reliability of the key. "
            "Songs with many key changes may correspond to low values in this field."
        ),
    )
    mode_confidence: IntervalFloat = Field(
        description="The confidence, from 0.0 to 1.0, of the reliability of the mode.",
    )


class _SpotifyAudioAnalysisSegment(_SpotifyAudioAnalysisInterval):
    loudness_start: Decibels = Field(
        description=(
            "The onset loudness of the segment in decibels (dB). Combined with loudness_max and loudness_max_time, "
            "these components can be used to describe the 'attack' of the segment."
        ),
    )
    loudness_max: Decibels = Field(
        description=(
            "The peak loudness of the segment in decibels (dB). Combined with loudness_start and loudness_max_time, "
            "these components can be used to describe the 'attack' of the segment."
        ),
    )
    loudness_max_time: Length = Field(
        description=(
            "The segment-relative offset of the segment peak loudness in seconds. Combined with loudness_start and "
            "loudness_max, these components can be used to desctibe the 'attack' of the segment."
        )
    )
    loudness_end: Decibels = Field(
        description=(
            "The offset loudness of the segment in decibels (dB). This value should be equivalent to the "
            "loudness_start of the following segment."
        ),
    )
    pitches: list[IntervalFloat] = Field(
        description=(
            "Pitch content is given by a “chroma” vector, corresponding to the 12 pitch classes C, C#, D to B, with "
            "values ranging from 0 to 1 that describe the relative dominance of every pitch in the chromatic scale. "
            "For example a C Major chord would likely be represented by large values "
            "of C, E and G (i.e. classes 0, 4, and 7)."
        ),
    )
    timbre: list[float] = Field(
        description=(
            "Timbre is the quality of a musical note or sound that distinguishes different types of musical "
            "instruments, or voices. It is a complex notion also referred to as sound color, texture, or tone quality, "
            "and is derived from the shape of a segment’s spectro-temporal surface, independently of pitch and "
            "loudness. The timbre feature is a vector that includes 12 unbounded values roughly centered around 0. "
            "Those values are high level abstractions of the spectral surface, ordered by degree of importance."
        )
    )


class SpotifyAudioAnalysis(SpotifyModel):
    meta: _SpotifyAudioAnalysisMeta = Field(
        description="Metadata about the audio analysis of this track.",
    )
    track: _SpotifyAudioAnalysisTrack = Field(
        description="Audio analysis data about this track.",
    )
    bars: list[_SpotifyAudioAnalysisInterval] = Field(
        description=(
            "The time intervals of the bars throughout the track. "
            "A bar (or measure) is a segment of time defined as a given number of beats."
        ),
    )
    beats: list[_SpotifyAudioAnalysisInterval] = Field(
        description=(
            "The time intervals of beats throughout the track. A beat is the basic time unit of a piece of music; "
            "for example, each tick of a metronome. Beats are typically multiples of tatums."
        ),
    )
    sections: list[_SpotifyAudioAnalysisSection] = Field(
        description=(
            "Sections are defined by large variations in rhythm or timbre, e.g. chorus, verse, bridge, guitar solo, "
            "etc. Each section contains its own descriptions of tempo, key, mode, time_signature, and loudness."
        ),
    )
    segments: list[_SpotifyAudioAnalysisSegment] = Field(
        description="Each segment contains a roughly conisistent sound throughout its duration."
    )
    tatums: list[_SpotifyAudioAnalysisInterval] = Field(
        description=(
            "A tatum represents the lowest regular pulse train that a listener intuitively infers from the "
            "timing of perceived musical events (segments)."
        ),
    )
