"""Independent image-generation provider management."""

from Frontend.core.icons import ProviderIcon

from Frontend.pages.providers.provider_settings import MediaProviderPage


class ImageGenerationPage(MediaProviderPage):
    KIND = "image_generation"
    TITLE = "生图接口"
    ICON = ProviderIcon.IMAGE_GENERATION
