import os

from PyQt5.QtCore import QVariant, Qt
from PyQt5.QtWidgets import QTreeWidgetItem, QVBoxLayout
from qfluentwidgets import CardWidget, StrongBodyLabel, TreeWidget

from ModuleFolders.Base.Base import Base
from ModuleFolders.Config.Config import ConfigMixin
from ModuleFolders.Log.Log import LogMixin
from UserInterface.Widget.Toast import ToastMixin


class NavigationCard(ConfigMixin, LogMixin, ToastMixin, Base, CardWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 10, 10, 10)
        self.layout.setSpacing(8)

        self.title_label = StrongBodyLabel(self.tra("项目文件"), self)
        self.title_label.setAlignment(Qt.AlignCenter)
        self.layout.addWidget(self.title_label)

        self.tree = TreeWidget(self)
        self.tree.setHeaderHidden(True)
        self.layout.addWidget(self.tree)

    def update_tree(self, hierarchy: dict) -> None:
        self.tree.clear()

        if not hierarchy:
            return

        folder_items = {}

        for dir_path in sorted(hierarchy.keys()):
            if dir_path == ".":
                parent_item = self.tree.invisibleRootItem()
            else:
                parts = dir_path.replace("\\", "/").split("/")
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

            for filename in hierarchy[dir_path]:
                full_path = os.path.join(dir_path, filename) if dir_path != "." else filename
                file_item = QTreeWidgetItem([filename])
                file_item.setData(0, Qt.UserRole, QVariant(full_path))
                parent_item.addChild(file_item)

        self.tree.expandAll()
