"""Inline prompt editing shared by text and image settings."""

import copy
import uuid

from qfluentwidgets import FluentIcon, LineEdit, MessageBox, PrimaryPushButton

from Frontend.components.toast import ToastMixin
from Frontend.pages.prompts.prompt_library_page import AddEditPromptDialog, PromptLibraryPage


class EditablePromptLibraryPage(PromptLibraryPage, ToastMixin):
    def __init__(self, *args, **kwargs):
        self._refreshing = True
        self._inline_ready = False
        self._baseline = None
        self._new_prompt_id = None
        super().__init__(*args, **kwargs)
        toolbar = self.preview_toolbar.layout()
        self.name_input = LineEdit(self.preview_toolbar)
        self.name_input.setMaxLength(100)
        self.name_input.setPlaceholderText(self.tra("提示词名称"))
        self.name_input.setAccessibleName(self.tra("提示词名称"))
        toolbar.insertWidget(0, self.name_input, 1)
        self.save_prompt_button = PrimaryPushButton(FluentIcon.SAVE, self.tra("保存修改"), self.status_bar)
        self.save_prompt_button.clicked.connect(self.save_current_prompt)
        self.status_bar.setFixedHeight(52)
        self.mode_label = self.status_bar.layout().itemAt(3).widget()
        self.status_bar.layout().addWidget(self.save_prompt_button)
        self.selected_prompt_content_text.setMaximumWidth(16777215)
        self.name_input.textChanged.connect(self._update_dirty_status)
        self.selected_prompt_content_text.textChanged.connect(self._update_dirty_status)
        self._inline_ready = True
        self.display_prompt_details(self.selected_prompt_card.prompt_data, persist=False)
        self._refreshing = False

    def _form(self):
        return self.name_input.text().strip(), self.selected_prompt_content_text.toPlainText()

    def _is_dirty(self):
        return self._inline_ready and self._baseline is not None and (
            self._new_prompt_id is not None or self._form() != self._baseline
        )

    def _update_dirty_status(self):
        if not self._inline_ready or self._refreshing:
            return
        dirty = self._is_dirty()
        self.active_label.setText(self.tra("待保存") if dirty else self.tra("使用中"))
        self.save_prompt_button.setEnabled(dirty)
        self.character_count_label.setText(self.tra("{count} 字符").format(count=f"{len(self.selected_prompt_content_text.toPlainText()):,}"))

    def display_prompt_details(self, prompt_data, *, persist=True):
        if self._inline_ready and not self._refreshing and persist:
            if not self.prepare_to_leave():
                return
            self._commit_change(selected_id=prompt_data["id"])
            return
        super().display_prompt_details(prompt_data, persist=False)
        if not self._inline_ready:
            return
        self._refreshing = True
        is_user = prompt_data.get("type") == "user"
        self.name_input.setText(prompt_data["name"])
        self.name_input.setVisible(is_user)
        self.selected_prompt_name_label.setVisible(not is_user)
        self.selected_prompt_content_text.setReadOnly(not is_user)
        self.edit_prompt_button.hide()
        self.save_prompt_button.setVisible(is_user)
        self.mode_label.setText(self.tra("返回或切换时保存") if is_user else self.tra("系统预设只读"))
        self._baseline = self._form()
        self._refreshing = False
        self._update_dirty_status()

    def _apply_config(self, config):
        prompts = self._read_user_prompts(config)
        self._new_prompt_id = None
        self.user_prompts = prompts
        self._refreshing = True
        try:
            self.update_prompt_cards(config.get(self.selection_key, {}).get("last_selected_id"))
        finally:
            self._refreshing = False
        self._update_dirty_status()

    def _read_user_prompts(self, config):
        return copy.deepcopy(config.get(self.user_data_key, []))

    def _validate_user_prompt(self, prompt):
        return prompt

    def showEvent(self, event):
        super().showEvent(event)
        if self._inline_ready and not self._is_dirty():
            try:
                self._apply_config(self.load_config())
            except Exception:
                self.error_toast(self.tra("读取失败"), self.tra("无法读取任务设置，请检查后端连接后重新打开此页面。"))

    def _commit_change(self, *, selected_id=None, edit=None, delete_id=None):
        try:
            edit = self._validate_user_prompt(edit) if edit is not None else None

            def update(config):
                prompts = self._read_user_prompts(config)
                active = self.selected_prompt_id if selected_id is None else selected_id
                if edit is not None:
                    index = next((i for i, item in enumerate(prompts) if item["id"] == edit["id"]), None)
                    if index is None:
                        if self._new_prompt_id != edit["id"]:
                            raise ValueError(self.tra("所选提示词已不存在，请重新打开页面后选择。"))
                        prompts.append(edit)
                    else:
                        prompts[index] = edit
                    active = edit["id"]
                if delete_id is not None:
                    prompts = [p for p in prompts if p["id"] != delete_id]
                    if active == delete_id:
                        active = self.default_prompt[0]["id"]
                chosen = next((p for p in self.default_prompt + prompts if p["id"] == active), None)
                if chosen is None:
                    raise ValueError(self.tra("所选提示词已不存在，请重新打开页面后选择。"))
                config[self.selection_key] = {"last_selected_id": active, "prompt_content": chosen["content"]}
                config[self.user_data_key] = prompts
            config = self.update_config(update)
            self._apply_config(config)
            return True
        except ValueError as error:
            self.error_toast(self.tra("配置无效"), self.tra(str(error)))
            return False
        except Exception as error:
            self.error_toast(self.tra("保存失败"), self.tra("修改尚未保存，请检查后端连接后重试。") + "\n" + str(error))
            return False

    def save_current_prompt(self):
        if not self._is_dirty():
            return True
        name, content = self._form()
        if not name or not content.strip() or "\x00" in name + content:
            self.error_toast(self.tra("配置无效"), self.tra("请填写提示词名称和内容，且不要包含空字符。"))
            return False
        return self._commit_change(edit={"id": self.selected_prompt_id, "name": name, "content": content, "type": "user"})

    def prepare_to_leave(self):
        return self.save_current_prompt()

    def _new_draft(self, name, content):
        if not self.prepare_to_leave():
            return
        prompt = {"id": str(uuid.uuid4()), "name": name, "content": content, "type": "user"}
        self._new_prompt_id = prompt["id"]
        self.user_prompts.append(prompt)
        self.search_edit.clear()
        self._refreshing = True
        self.update_prompt_cards(prompt["id"])
        self._refreshing = False
        self._update_dirty_status()
        self.name_input.setFocus()
        self.name_input.selectAll()

    def open_add_prompt_dialog(self, _checked=False):
        if not self.prepare_to_leave():
            return
        dialog = AddEditPromptDialog(parent=self)
        dialog.name_edit.setMaxLength(self.name_input.maxLength())
        accepted = dialog.exec_()
        data = dialog.get_data() if accepted else None
        dialog.deleteLater()
        if not data:
            return
        self._new_draft(data["name"], data["content"])
        # A failed save leaves the entered content in the inline editor for retry.
        if self.save_current_prompt():
            self.scroll_area.ensureWidgetVisible(self.selected_prompt_card)

    def delete_user_prompt(self, prompt_id):
        if not any(p["id"] == prompt_id for p in self.user_prompts):
            return False
        dialog = MessageBox(self.tra("删除提示词"), self.tra("删除此自定义提示词及尚未保存的修改？"), self.window())
        dialog.yesButton.setText(self.tra("删除"))
        dialog.cancelButton.setText(self.tra("取消"))
        accepted = dialog.exec()
        dialog.deleteLater()
        if not accepted:
            return False
        if prompt_id == self._new_prompt_id:
            try:
                self._apply_config(self.load_config())
                return True
            except Exception as error:
                self.error_toast(self.tra("读取失败"), str(error))
                return False
        return self._commit_change(delete_id=prompt_id)
