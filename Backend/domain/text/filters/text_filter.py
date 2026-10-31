from Backend.domain.config.task_config import TaskConfig
from Backend.domain.models.cache_project import CacheProject
from Backend.domain.text.filters.code_text_filter import CodeTextFilter
from Backend.domain.text.filters.general_text_filter import GeneralTextFilter
from Backend.domain.text.filters.language_filter import LanguageFilter
from Backend.domain.text.filters.special_text_filter import SpecialTextFilter


class TextFilter:
    def __init__(self) -> None:
        self.general_text_filter = GeneralTextFilter()
        self.language_text_filter = LanguageFilter()
        self.code_text_filter = CodeTextFilter()
        self.special_text_filter = SpecialTextFilter()

    def filter_project(self, config: TaskConfig, project: CacheProject) -> None:
        self.general_text_filter.filter_text(project)

        if getattr(config, "language_filter_switch", True):
            self.language_text_filter.filter_text(config, project)

        if getattr(config, "code_filter_switch", False):
            self.code_text_filter.filter_text(project)

        self.special_text_filter.filter_text(project)
