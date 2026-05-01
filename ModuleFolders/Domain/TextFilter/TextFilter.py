from ModuleFolders.Infrastructure.TaskConfig.TaskConfig import TaskConfig
from ModuleFolders.Service.Cache.CacheProject import CacheProject

from ModuleFolders.Domain.TextFilter.GeneralTextFilter import GeneralTextFilter
from ModuleFolders.Domain.TextFilter.LanguageFilter import LanguageFilter
from ModuleFolders.Domain.TextFilter.SpecialTextFilter import SpecialTextFilter


class TextFilter:
    def __init__(self) -> None:
        self.general_text_filter = GeneralTextFilter()
        self.language_text_filter = LanguageFilter()
        self.special_text_filter = SpecialTextFilter()

    def filter_project(self, config: TaskConfig, project: CacheProject) -> None:
        self.general_text_filter.filter_text(project)

        if getattr(config, "language_filter_switch", True):
            self.language_text_filter.filter_text(config, project)

        self.special_text_filter.filter_text(project)
