"""Dispatch the configured speech protocol without changing paid services."""
from Backend.application.pipeline_common import PipelineError
from Backend.infrastructure.transcription import dashscope, minimax, openai, volcengine


SUPPORTED_FORMATS = dashscope.SUPPORTED_FORMATS | volcengine.FAST_FORMATS | minimax.SUPPORTED_FORMATS | openai.SUPPORTED_FORMATS


def request_transcription(audio_bytes, *, audio_format, sample_rate, duration_ms, config, context=None,
                          retry_context=None):
    arguments = {"audio_format": audio_format, "sample_rate": sample_rate, "duration_ms": duration_ms,
                 "config": config, "context": context, "retry_context": retry_context}
    if config["api_format"] == "DashScope":
        return dashscope.request_transcription(audio_bytes, **arguments)
    if config["api_format"] == "OpenAI":
        return openai.request_transcription(audio_bytes, **arguments)
    if config["api_format"] == "MiniMax":
        return minimax.request_transcription(audio_bytes, **arguments)
    if config["api_format"] == "VolcengineASRFast":
        return volcengine.request_fast(audio_bytes, **arguments)
    raise PipelineError("ASR_CONFIG_ERROR", "未知的转录协议", 400, {"attempts": 0})
