"""Video contracts reuse ASR, translation and subtitle options."""
from typing import Literal

from Backend.api.audio_schemas import AudioReadRequest, AudioTranslateRequest, AudioTranslateResponse, SubtitleOptions


class VideoReadRequest(AudioReadRequest):
    pass


class VideoSubtitleOptions(SubtitleOptions):
    mode: Literal["translated", "source", "bilingual"] = "bilingual"


class VideoTranslateRequest(AudioTranslateRequest):
    output: VideoSubtitleOptions


class VideoTranslateResponse(AudioTranslateResponse):
    pass
