"""Independent OCR provider management."""

from qfluentwidgets import FluentIcon

from Frontend.pages.providers.provider_settings import MediaProviderPage


class OcrPage(MediaProviderPage):
    KIND = "ocr"
    TITLE = "OCR 接口"
    ICON = FluentIcon.PHOTO
