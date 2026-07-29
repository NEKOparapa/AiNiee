from magika import Magika
from magika.types.content_type_label import ContentTypeLabel

from ModuleFolders.Service.Cache.CacheItem import TranslationStatus
from ModuleFolders.Service.Cache.CacheProject import CacheProject, ProjectType


class CodeTextFilter:
    magika = Magika()
    SUPPORT_PROJECT_TYPES = frozenset([ProjectType.MTOOL])

    def get_label(self, text: str) -> ContentTypeLabel:
        result = self.magika.identify_bytes(text.encode())
        return result.output.label

    def filter_text(self, event_data: CacheProject):
        for item in event_data.items_iter(self.SUPPORT_PROJECT_TYPES):
            if item.translation_status != TranslationStatus.UNTRANSLATED:
                continue
            label = self.get_label(item.source_text)
            if label != ContentTypeLabel.TXT:
                item.translation_status = TranslationStatus.TRANSLATED
