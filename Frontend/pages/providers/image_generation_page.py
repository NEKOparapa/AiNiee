"""Independent image-generation provider management."""

from qfluentwidgets import FluentIcon

from Frontend.pages.providers.provider_settings import MediaProviderPage


class ImageGenerationPage(MediaProviderPage):
    KIND = "image_generation"
    TITLE = "生图接口"
    ICON = FluentIcon.PHOTO
