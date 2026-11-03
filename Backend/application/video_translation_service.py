"""Video uses the shared speech pipeline with its own task settings."""
from Backend.application.audio_translation_service import translate_speech_media
from Backend.application.pipeline_common import PipelineError
from Backend.domain.config.transcription_config import TranscriptionConfig


def video_subtitle_options(output):
    if output is not None and not isinstance(output, dict):
        raise PipelineError("VALIDATION_ERROR", "视频字幕导出设置必须为对象", 422)
    settings = TranscriptionConfig.read_snapshot()["video_translation_settings"]
    if not isinstance(settings, dict) or not isinstance(settings.get("export", {}), dict):
        raise PipelineError("VALIDATION_ERROR", "视频字幕导出设置必须为对象", 422)
    saved = settings.get("export", {})
    return {"format": "srt", "mode": "bilingual", **saved, **(output or {})}


def translate_video(path, *, read_options=None, transcription=None, translation=None, output=None, context=None):
    return translate_speech_media(path, kind="video", read_options=read_options, transcription=transcription,
                                  translation=translation, output=video_subtitle_options(output), context=context)
