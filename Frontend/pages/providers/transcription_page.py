"""Independent transcription providers and compatibility exports."""

from Frontend.core.icons import ProviderIcon
from Frontend.core.media_provider_config import (
    DEFAULT_TRANSCRIPTION_PLATFORM,
    SUPPORTED_LANGUAGE_HINTS, build_media_provider_update, normalize_media_provider,
    validate_media_provider,
)
from Frontend.pages.providers.provider_settings import MediaProviderPage


def normalize_transcription_platform(data=None):
    return normalize_media_provider("transcription", data)


def validate_transcription_platform(data, *, require_api_key=False):
    return validate_media_provider("transcription", data, require_credentials=require_api_key)


def build_transcription_config_update(config, platform_id, platform=None, *, action="save"):
    return build_media_provider_update(config, "transcription", platform_id, platform, action=action)


class TranscriptionPage(MediaProviderPage):
    KIND = "transcription"
    TITLE = "转录接口"
    ICON = ProviderIcon.TRANSCRIPTION
