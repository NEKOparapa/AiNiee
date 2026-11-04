import posixpath

from PyQt5.QtCore import QVariant, Qt
from PyQt5.QtWidgets import QTreeWidgetItem, QVBoxLayout
from qfluentwidgets import CardWidget, FluentIcon as FIF, StrongBodyLabel, TransparentPushButton, TreeWidget, setFont

from Frontend.core.base import Base
from Frontend.core.config import ConfigMixin
from Frontend.core.log import LogMixin
from Frontend.components.toast import ToastMixin


class NavigationCard(ConfigMixin, LogMixin, ToastMixin, Base, CardWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 10, 10, 10)
        self.layout.setSpacing(8)

        self.title_label = StrongBodyLabel(self.tra("项目文件"), self)
        setFont(self.title_label, 12)
        self.title_label.setAlignment(Qt.AlignCenter)
        self.layout.addWidget(self.title_label)

        self.tree = TreeWidget(self)
        self.tree.setHeaderHidden(True)
        self.layout.addWidget(self.tree, 1)

        self.search_button = TransparentPushButton(FIF.SEARCH, self.tra("搜索"), self)
        self.search_button.setFixedHeight(32)
        self.layout.addWidget(self.search_button)

    def update_tree(self, file_paths: list[str]) -> None:
        self.tree.clear()

        if not file_paths:
            return

        # Normalize only the display hierarchy. File actions must retain the
        # exact cache key, including separators used by older project caches.
        hierarchy = {}
        for file_path in file_paths:
            directory, filename = posixpath.split(file_path.replace("\\", "/"))
            hierarchy.setdefault(directory or ".", []).append((filename, file_path))

        folder_items = {}

        for dir_path in sorted(hierarchy.keys()):
            if dir_path == ".":
                parent_item = self.tree.invisibleRootItem()
            else:
                parts = dir_path.split("/")
                current_path = ""
                parent_item = self.tree.invisibleRootItem()

                for part in parts:
                    current_path = part if not current_path else f"{current_path}/{part}"

                    if current_path not in folder_items:
                        new_folder_item = QTreeWidgetItem([part])
                        new_folder_item.setData(0, Qt.UserRole, None)
                        parent_item.addChild(new_folder_item)
                        folder_items[current_path] = new_folder_item
                        parent_item = new_folder_item
                    else:
                        parent_item = folder_items[current_path]

            for filename, file_path in sorted(hierarchy[dir_path]):
                file_item = QTreeWidgetItem([filename])
                file_item.setData(0, Qt.UserRole, QVariant(file_path))
                parent_item.addChild(file_item)

        self.tree.expandAll()
