"""Independent video task settings using the shared speech settings form."""
from Frontend.pages.settings.audio_translation_settings_page import AudioTranslationSettingsPage


class VideoTranslationSettingsPage(AudioTranslationSettingsPage):
    def __init__(self, text, parent=None):
        super().__init__(text, parent, kind="video")
